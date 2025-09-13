import streamlit as st
import os
import yt_dlp
import shutil
import tempfile
import zipfile
from contextlib import contextmanager
import json

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
# 2. 핵심 함수 (진단 기능 함수 추가)
# --------------------------------------------------------------------------

@contextmanager
def temporary_directory():
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)

def get_video_info(url):
    """다운로드 없이 영상의 메타데이터만 추출하여 반환합니다."""
    ydl_opts = {'quiet': True, 'noprogress': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            return info_dict
    except yt_dlp.utils.DownloadError as e:
        # 오류 발생 시, 오류 메시지 텍스트를 반환
        return {"error": str(e)}

def download_content(url, download_type, quality, container, temp_dir):
    """사용자 선택에 따라 유튜브 콘텐츠를 다운로드하는 통합 함수 (단일 파일 전용)."""

    output_template = os.path.join(temp_dir, '%(title)s [%(id)s].%(ext)s')
    
    # ------------------ ydl_opts 설정 (핵심 수정) ------------------
    ydl_opts = {
        'outtmpl': output_template,
        'noplaylist': True,
        'quiet': True,
        'noprogress': True,
        'retries': 10,
        'fragment_retries': 10,
        # --- 추가된 부분: 일반 브라우저처럼 보이게 하기 위한 User-Agent ---
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        },
    }

    if download_type == '오디오':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': container,
                'preferredquality': quality,
            }],
            'keepvideo': False, 
        })
    else:  # '영상'
        quality_filter = f'[height<=?{quality.replace("p", "")}]' if quality != 'best' else ''
        ydl_opts.update({
            'format': f'bestvideo{quality_filter}[ext=mp4]+bestaudio[ext=m4a]/bestvideo{quality_filter}+bestaudio/best',
            'merge_output_format': container,
        })

    # --- (이하 다운로드 로직은 이전과 동일) ---
    final_filepath = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            ydl.download([url])

            if download_type == '오디오':
                base_filename, _ = os.path.splitext(ydl.prepare_filename(info_dict))
                final_filepath = f"{base_filename}.{container}"
            else:
                final_filepath = ydl.prepare_filename(info_dict)

            if not os.path.exists(final_filepath):
                 raise FileNotFoundError(f"예상 경로에 파일이 없습니다: {final_filepath}")

    except yt_dlp.utils.DownloadError as e:
        error_message = str(e)
        if "Video unavailable" in error_message or "is not available" in error_message:
            raise ValueError("영상을 찾을 수 없습니다. 삭제, 비공개, 국가 제한 등의 원인일 수 있습니다.")
        # --- 403 오류에 대한 명확한 안내 추가 ---
        elif "HTTP Error 403: Forbidden" in error_message:
            raise ValueError("유튜브에서 다운로드를 차단했습니다 (오류 403). 잠시 후 다시 시도하거나 다른 영상으로 테스트해주세요.")
        else:
            raise ValueError(f"다운로드 중 오류가 발생했습니다: {error_message}")
    except Exception as e:
        raise RuntimeError(f"알 수 없는 오류가 발생했습니다: {e}")

    if not final_filepath or not os.path.exists(final_filepath):
        raise FileNotFoundError(f"다운로드 후 '{container}' 파일을 찾을 수 없습니다. 다시 시도해주세요.")
    
    display_name = os.path.basename(final_filepath)
    mime_type_map = {'mp4': 'video/mp4', 'mkv': 'video/x-matroska', 'mp3': 'audio/mpeg', 'flac': 'audio/flac', 'm4a': 'audio/mp4', 'wav': 'audio/wav'}
    mime_type = mime_type_map.get(container, 'application/octet-stream')

    return final_filepath, display_name, mime_type

def get_image_base64(image_path):
    """이미지 파일을 Base64로 인코딩하여 반환합니다."""
    import base64
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        return None

# --------------------------------------------------------------------------
# 3. Streamlit UI 및 로직 구현 (진단 기능 버튼 추가)
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
    url = st.text_input("다운로드할 YouTube URL을 입력하세요.", placeholder="https://www.youtube.com/watch?v=...")

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
    
    # --- UI 수정: 버튼을 두 개로 분리 ---
    action_col1, action_col2 = st.columns(2)
    
    with action_col1:
        if st.button("다운로드 시작", use_container_width=True, type="primary"):
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
                                data=file_bytes, file_name=display_name, mime=mime_type,
                                use_container_width=True, key=f"download_{display_name}"
                            )
                        except Exception as e:
                            st.error(f"오류: {e}")
            else:
                st.warning("유튜브 URL을 입력해주세요.")

    with action_col2:
        if st.button("상세 정보 확인", use_container_width=True):
            if url:
                with st.spinner("유튜브로부터 상세 정보를 가져오는 중..."):
                    info = get_video_info(url)
                    
                    if "error" in info:
                        st.error("정보를 가져오는 데 실패했습니다.")
                        # 에러의 상세 내용을 보여주어 원인 파악을 돕습니다.
                        with st.expander("에러 원문 보기"):
                            st.code(info["error"])
                    else:
                        st.success(f"**'{info.get('title', '제목 없음')}'** 의 정보를 성공적으로 가져왔습니다.")
                        with st.expander("자세한 원본 데이터 보기 (JSON)"):
                            st.json(info)
            else:
                st.warning("정보를 확인할 유튜브 URL을 입력해주세요.")

# --------------------------------------------------------------------------
# 4. 인증 로직 및 앱 실행 (기존과 동일)
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

