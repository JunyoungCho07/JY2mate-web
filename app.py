import streamlit as st
import os
import yt_dlp
import shutil
import tempfile
import zipfile
from contextlib import contextmanager
import base64

# --------------------------------------------------------------------------
# 1. 페이지 설정 및 스타일링
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="JY2mate | YouTube Downloader",
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="auto"
)

# 사용자 정의 CSS로 디자인 개선
st.markdown("""
<style>
    /* 전체 폰트 및 배경 설정 */
    html, body, [class*="st-"] {
        font-family: ' Pretendard', sans-serif;
    }
    /* 버튼 스타일 */
    .stButton>button {
        background-color: #FF4B4B;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 10px 20px;
        font-weight: bold;
        transition: background-color 0.3s;
    }
    .stButton>button:hover {
        background-color: #E03C3C;
    }
    /* 다운로드 버튼 스타일 */
    .stDownloadButton>button {
        background-color: #4CAF50;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 10px 20px;
        font-weight: bold;
        width: 100%;
        transition: background-color 0.3s;
    }
    .stDownloadButton>button:hover {
        background-color: #45a049;
    }
    /* 입력창 및 라디오 버튼 컨테이너 */
    .st-emotion-cache-1r6slb0 {
        border: 1px solid #e0e0e0;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    /* 제목 스타일 */
    h1 {
        color: #333;
        text-align: center;
    }
    p {
        text-align: center;
        color: #666;
    }
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------------------------------
# 2. 핵심 함수 정의
# --------------------------------------------------------------------------

@contextmanager
def temporary_directory():
    """임시 디렉토리를 생성하고 사용 후 정리하는 컨텍스트 관리자"""
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)

def download_content(url, download_type, quality, temp_dir):
    """
    yt-dlp를 사용하여 비디오 또는 오디오를 다운로드하는 함수.
    성공 시 (파일 경로, 파일명, MIME 타입) 튜플을 반환하고, 실패 시 예외를 발생시킵니다.
    """
    # yt-dlp 옵션 설정
    if download_type == '오디오 (MP3)':
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': quality,
            }],
            'quiet': True,
            'ignoreerrors': True,
            'noprogress': True,
        }
    else: # 영상 (MP4)
        # --- 핵심 수정 부분 ---
        # 확장자를 특정하지 않고, 화질만으로 최적의 포맷을 선택하도록 수정
        # yt-dlp가 webm 등 다른 포맷의 영상/음성을 가져와도 최종적으로 mp4로 합쳐줍니다.
        quality_filter = f'[height<=?{quality.replace("p", "")}]' if quality != 'best' else ''
        ydl_opts = {
            'format': f'bestvideo{quality_filter}+bestaudio/best',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'merge_output_format': 'mp4', # 최종 결과물은 항상 mp4로 만듭니다.
            'quiet': True,
            'ignoreerrors': True,
            'noprogress': True,
        }
    
    # 정보 추출 및 다운로드
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        
        downloaded_files = [f for f in os.listdir(temp_dir) if not f.endswith('.zip')]
        if not downloaded_files:
            raise ValueError("파일을 다운로드하지 못했습니다. URL이 올바르거나 비공개 영상이 아닌지 확인해주세요.")

        # 재생목록 여부 확인 (실제 항목이 2개 이상일 때만 재생목록으로 간주)
        is_playlist = 'entries' in info_dict and info_dict['entries'] and len(info_dict['entries']) > 1
        
        if is_playlist:
            playlist_title = info_dict.get('title', 'playlist')
            safe_playlist_title = "".join([c for c in playlist_title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
            zip_filename = f"{safe_playlist_title}.zip"
            zip_filepath = os.path.join(temp_dir, zip_filename)

            with zipfile.ZipFile(zip_filepath, 'w') as zipf:
                for file in downloaded_files:
                    zipf.write(os.path.join(temp_dir, file), arcname=file)
            
            return zip_filepath, zip_filename, 'application/zip'

        else:
            # 단일 파일 처리
            # 최종적으로 합쳐진 mp4 파일을 찾아야 합니다.
            final_file = None
            for file in downloaded_files:
                if file.endswith('.mp4'):
                    final_file = file
                    break
            
            if not final_file:
                 raise FileNotFoundError("최종 mp4 파일을 찾을 수 없습니다. 다운로드 과정에 문제가 발생했을 수 있습니다.")

            file_path = os.path.join(temp_dir, final_file)
            mime_type = 'video/mp4'
            return file_path, final_file, mime_type
        
def get_image_base64(path):
    try:
        with open(path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode('utf-8')
    except FileNotFoundError:
        return None


# --------------------------------------------------------------------------
# 3. Streamlit UI 및 로직 구현
# --------------------------------------------------------------------------

def run_app():
    """메인 애플리케이션을 실행하는 함수"""
    image_path = "JYC_clear.png"
    image_base64 = get_image_base64(image_path)
    if image_base64:
        st.markdown(f"""<div style="text-align: center;"><img src="data:image/png;base64,{image_base64}" alt="로고" style="width:180px; margin-bottom: 20px;"></div>""", unsafe_allow_html=True)
    st.title("🎬 JY2mate")
    st.markdown("<p>유튜브 영상과 오디오를 간편하게 다운로드하세요.</p><br>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Developed by JunyoungCho</p>", unsafe_allow_html=True)
    
    # URL 입력
    url = st.text_input("다운로드할 YouTube URL을 입력하세요.", placeholder="https://www.youtube.com/watch?v=...")

    # 다운로드 옵션
    col1, col2 = st.columns(2)
    with col1:
        download_type = st.radio(
            "다운로드 타입",
            ('오디오 (MP3)', '영상 (MP4)'),
            horizontal=True
        )

    with col2:
        if download_type == '오디오 (MP3)':
            quality = st.selectbox(
                "음질 선택 (kbps)",
                ('192', '320', '128'),
            )
            st.caption("숫자가 높을수록 음질이 좋습니다.")
        else:
            quality = st.selectbox(
                "화질 선택",
                ('720p', '1080p', '480p', 'best'),
            )
            st.caption("'best'는 다운로드 가능한 최고 화질입니다.")
            
    # 다운로드 버튼
    if st.button("다운로드 시작", use_container_width=True):
        if url:
            with st.spinner('다운로드를 준비 중입니다... 잠시만 기다려주세요.'):
                with temporary_directory() as temp_dir:
                    try:
                        final_path, display_name, mime_type = download_content(url, download_type, quality, temp_dir)

                        st.success(f"**{display_name}** 다운로드가 완료되었습니다!")
                        
                        with open(final_path, 'rb') as f:
                            file_bytes = f.read()

                        st.download_button(
                            label=f"📥 '{display_name}' 다운로드",
                            data=file_bytes,
                            file_name=display_name,
                            mime=mime_type,
                            use_container_width=True,
                            key=f"download_{display_name}" # 상태 유지를 위한 고유 키 추가
                        )
                    
                    except Exception as e:
                        st.error(f"다운로드 중 오류가 발생했습니다: {e}")
        else:
            st.warning("유튜브 URL을 입력해주세요.")


# --------------------------------------------------------------------------
# 4. 인증 로직 및 앱 실행
# --------------------------------------------------------------------------
def check_authentication():
    """비밀 코드를 확인하여 인증을 처리합니다."""
    try:
        correct_password = st.secrets["LICENSE_CODE"]
    except (FileNotFoundError, KeyError):
        st.error("Secrets.toml 파일에 LICENSE_CODE가 설정되지 않았습니다.")
        st.info("`.streamlit/secrets.toml` 파일을 생성하고 `LICENSE_CODE = \"your_code\"` 형식으로 인증 코드를 추가해주세요.")
        return False
        
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False

    if not st.session_state['authenticated']:
        # st.form을 사용하여 Enter 키로 제출 기능 구현
        with st.sidebar.form("auth_form"):
            password = st.text_input("인증 코드를 입력하세요", type="password")
            submitted = st.form_submit_button("인증")
            
            if submitted:
                if password == correct_password:
                    st.session_state['authenticated'] = True
                    st.rerun()
                else:
                    st.sidebar.error("코드가 올바르지 않습니다.")
        return False
    else:
        return True

# 앱 실행
if check_authentication():
    run_app()
else:
    st.info("사이드바에서 인증 코드를 입력하여 앱 사용을 시작하세요.")

