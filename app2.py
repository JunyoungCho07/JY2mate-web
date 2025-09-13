import streamlit as st
import os
import yt_dlp
import shutil
import tempfile
import zipfile
from contextlib import contextmanager

# --------------------------------------------------------------------------
# 1. 페이지 설정 및 스타일링 (기존과 동일)
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="JY2mate | YouTube Downloader",
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="auto"
)

st.markdown("""
<style>
    html, body, [class*="st-"] { font-family: ' Pretendard', sans-serif; }
    .stButton>button { background-color: #FF4B4B; color: white; border-radius: 8px; border: none; padding: 10px 20px; font-weight: bold; transition: background-color 0.3s; }
    .stButton>button:hover { background-color: #E03C3C; }
    .stDownloadButton>button { background-color: #4CAF50; color: white; border-radius: 8px; border: none; padding: 10px 20px; font-weight: bold; width: 100%; transition: background-color 0.3s; }
    .stDownloadButton>button:hover { background-color: #45a049; }
    h1 { color: #333; text-align: center; }
    p { text-align: center; color: #666; }
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------------------------------
# 2. 핵심 다운로드 함수 (대폭 수정)
# --------------------------------------------------------------------------

@contextmanager
def temporary_directory():
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)

def download_content(url, download_type, quality, container, temp_dir):
    """
    사용자 선택에 따라 유튜브 콘텐츠를 다운로드하는 통합 함수.
    """
    final_filepath = None
    
    # --- 1. yt-dlp 옵션 동적 설정 ---
    if download_type == '오디오':
        # 오디오 전용 포스트프로세서 설정
        postprocessors = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': container, # 사용자가 선택한 확장자로 코덱 설정
            'preferredquality': quality,
        }]
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'postprocessors': postprocessors,
            'quiet': True,
            'noprogress': True,
        }
    else: # '영상'
        quality_filter = f'[height<=?{quality.replace("p", "")}]' if quality != 'best' else ''
        ydl_opts = {
            'format': f'bestvideo{quality_filter}+bestaudio/best',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'merge_output_format': container, # 사용자가 선택한 확장자로 병합
            'quiet': True,
            'noprogress': True,
        }

    # --- 2. 다운로드 및 파일 경로 확정 ---
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        
        # yt-dlp가 반환한 정보에서 최종 파일 경로를 직접 가져옴 (가장 안정적인 방법)
        # 단일 파일 다운로드 시 'requested_downloads'가 비어있을 수 있어 info_dict 자체를 확인
        if info_dict.get('requested_downloads'):
             final_filepath = info_dict['requested_downloads'][0]['filepath']
        else: # 단일 파일의 경우, 최상위 레벨에 정보가 있을 수 있음
             final_filepath = info_dict.get('filepath') or os.path.join(temp_dir, f"{info_dict['title']}.{container}")


    if not final_filepath or not os.path.exists(final_filepath):
        # 파일이 생성되지 않았을 경우, 임시 폴더에서 직접 탐색 시도
        found_files = [f for f in os.listdir(temp_dir) if f.endswith(container)]
        if found_files:
            final_filepath = os.path.join(temp_dir, found_files[0])
        else:
            raise FileNotFoundError(f"다운로드 후 '{container}' 파일을 찾을 수 없습니다. URL이나 옵션을 확인해주세요.")

    # --- 3. 파일 정보 반환 ---
    display_name = os.path.basename(final_filepath)
    mime_type_map = {
        'mp4': 'video/mp4', 'mkv': 'video/x-matroska',
        'mp3': 'audio/mpeg', 'flac': 'audio/flac', 'm4a': 'audio/mp4', 'wav': 'audio/wav'
    }
    mime_type = mime_type_map.get(container, 'application/octet-stream')

    return final_filepath, display_name, mime_type

# --------------------------------------------------------------------------
# 3. Streamlit UI 및 로직 구현 (옵션 선택 기능 추가)
# --------------------------------------------------------------------------

def run_app():
    """메인 애플리케이션을 실행하는 함수"""
    st.title("🎬 JY2mate")
    st.markdown("<p>유튜브 영상과 오디오를 간편하게 다운로드하세요.</p><br>", unsafe_allow_html=True)
    
    url = st.text_input("다운로드할 YouTube URL을 입력하세요.", placeholder="https://www.youtube.com/watch?v=...")

    # --- UI 개선: 모든 옵션을 명확하게 선택 ---
    col1, col2, col3 = st.columns(3)
    
    with col1:
        download_type = st.radio("다운로드 타입", ('영상', '오디오'), horizontal=True)

    with col2:
        if download_type == '영상':
            quality = st.selectbox("화질 선택", ('1080p', '720p', '480p', 'best'))
        else: # 오디오
            quality = st.selectbox("음질 선택 (kbps)", ('192', '320', '128'))

    with col3:
        if download_type == '영상':
            container = st.selectbox("확장자 선택", ('mp4', 'mkv'))
        else: # 오디오
            container = st.selectbox("확장자 선택", ('mp3', 'flac', 'm4a', 'wav'))
            
    # 다운로드 버튼
    if st.button("다운로드 시작", use_container_width=True):
        if url:
            with st.spinner(f"'{download_type}' 다운로드를 시작합니다... (품질: {quality}, 포맷: {container})"):
                with temporary_directory() as temp_dir:
                    try:
                        final_path, display_name, mime_type = download_content(
                            url, download_type, quality, container, temp_dir
                        )

                        st.success(f"**{display_name}** 다운로드가 완료되었습니다!")
                        
                        with open(final_path, 'rb') as f:
                            file_bytes = f.read()

                        st.download_button(
                            label=f"📥 '{display_name}' 다운로드",
                            data=file_bytes,
                            file_name=display_name,
                            mime=mime_type,
                            use_container_width=True,
                            key=f"download_{display_name}"
                        )
                    
                    except Exception as e:
                        st.error(f"다운로드 중 오류가 발생했습니다: {e}")
        else:
            st.warning("유튜브 URL을 입력해주세요.")

# --------------------------------------------------------------------------
# 4. 인증 로직 및 앱 실행 (기존과 동일, Enter 키 포함)
# --------------------------------------------------------------------------
def check_authentication():
    try:
        correct_password = st.secrets["LICENSE_CODE"]
    except (FileNotFoundError, KeyError):
        st.error("Secrets.toml 파일에 LICENSE_CODE가 설정되지 않았습니다.")
        st.info("`.streamlit/secrets.toml` 파일을 생성하고 `LICENSE_CODE = \"your_code\"` 형식으로 인증 코드를 추가해주세요.")
        return False
        
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False

    if not st.session_state['authenticated']:
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

if check_authentication():
    run_app()
else:
    st.info("사이드바에서 인증 코드를 입력하여 앱 사용을 시작하세요.")