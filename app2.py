# -*- coding: utf-8 -*-

import streamlit as st
import os
import yt_dlp
import shutil
import tempfile
import zipfile
import base64
import random
from contextlib import contextmanager # << [수정 1] contextmanager 임포트

# --------------------------------------------------------------------------
# 1. 페이지 설정 및 스타일링 (기존과 동일)
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="JY2mate | YouTube Downloader",
    page_icon="JYC_clear.png",
    layout="centered",
    initial_sidebar_state="auto"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Pretendard', sans-serif; }
    .stButton>button { background-color: #FF4B4B; color: white; border-radius: 8px; border: none; padding: 10px 20px; font-weight: bold; transition: background-color 0.3s; }
    .stButton>button:hover { background-color: #E03C3C; }
    .stDownloadButton>button { background-color: #4CAF50; color: white; border-radius: 8px; border: none; padding: 10px 20px; font-weight: bold; width: 100%; transition: background-color 0.3s; }
    .stDownloadButton>button:hover { background-color: #45a049; }
    h1 { color: #333; text-align: center; }
    p { text-align: center; color: #666; }
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------------------------------
# 2. 핵심 함수
# --------------------------------------------------------------------------

# 여러 브라우저의 User-Agent 리스트
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/111.0',
]

# << [수정 2] use_cookie_from_secrets 함수를 사용하는 함수들보다 먼저 정의
@contextmanager
def use_cookie_from_secrets():
    """
    Streamlit Secrets에 저장된 쿠키 내용을 임시 파일로 만들어 그 경로를 제공하고,
    사용이 끝나면 파일을 자동으로 삭제하는 context manager.
    """
    if "YOUTUBE_COOKIES" in st.secrets and st.secrets["YOUTUBE_COOKIES"]:
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8', suffix='.txt') as temp_cookie_file:
            temp_cookie_file.write(st.secrets["YOUTUBE_COOKIES"])
            cookie_filepath = temp_cookie_file.name
        
        try:
            yield cookie_filepath
        finally:
            os.remove(cookie_filepath)
    else:
        yield None

def get_video_info(url):
    """다운로드 없이 영상의 메타데이터만 추출하여 반환합니다."""
    with use_cookie_from_secrets() as cookie_filepath:
        ydl_opts = {
            'quiet': True,
            'noprogress': True,
            'cookiefile': cookie_filepath,
            'http_headers': {'User-Agent': random.choice(USER_AGENTS)},
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                return info_dict
        except yt_dlp.utils.DownloadError as e:
            return {"error": str(e)}

def download_content(url, download_type, quality, container, is_playlist):
    """유튜브 콘텐츠를 다운로드하는 통합 함수."""
    with use_cookie_from_secrets() as cookie_filepath:
        with tempfile.TemporaryDirectory() as temp_dir:
            download_path = os.path.join(temp_dir, "downloads")
            os.makedirs(download_path)

            ydl_opts = {
                'outtmpl': os.path.join(download_path, '%(playlist_index)s - %(title)s.%(ext)s' if is_playlist else '%(title)s.%(ext)s'),
                'cookiefile': cookie_filepath,
                'quiet': True, 'noprogress': True, 'retries': 10, 'fragment_retries': 10,
                'http_headers': {'User-Agent': random.choice(USER_AGENTS)},
                'noplaylist': not is_playlist, 'ignoreerrors': is_playlist,
            }

            if download_type == '오디오':
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': container, 'preferredquality': quality}],
                    'keepvideo': False,
                })
            else: # 영상
                quality_filter = f'[height<=?{quality.replace("p", "")}]' if quality != 'best' else ''
                ydl_opts.update({
                    'format': f'bestvideo{quality_filter}[ext=mp4]+bestaudio[ext=m4a]/bestvideo{quality_filter}+bestaudio/best',
                    'merge_output_format': container,
                })

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(url, download=True)
                    if not is_playlist:
                        if download_type == '오디오' and info_dict.get('requested_downloads'):
                            final_filepath = info_dict['requested_downloads'][0]['filepath']
                        else:
                            final_filepath = ydl.prepare_filename(info_dict)
                        
                        if not os.path.exists(final_filepath):
                            found = False
                            for f in os.listdir(download_path):
                                if f.startswith(info_dict.get('title', ' ')):
                                    final_filepath = os.path.join(download_path, f)
                                    found = True
                                    break
                            if not found: raise FileNotFoundError("다운로드된 파일을 찾을 수 없습니다.")
                        
                        display_name = os.path.basename(final_filepath)
                        with open(final_filepath, "rb") as f:
                            file_data = f.read()
                        
                        mime_type_map = {'mp4': 'video/mp4', 'mkv': 'video/x-matroska', 'mp3': 'audio/mpeg', 'flac': 'audio/flac', 'm4a': 'audio/mp4', 'wav': 'audio/wav'}
                        mime_type = mime_type_map.get(os.path.splitext(display_name)[1].lower().strip('.'), 'application/octet-stream')
                        return file_data, display_name, mime_type

            except yt_dlp.utils.DownloadError as e:
                error_message = str(e)
                if "Video unavailable" in error_message: raise ValueError("영상을 찾을 수 없습니다. 삭제, 비공개, 국가 제한 등의 원인일 수 있습니다.")
                elif "HTTP Error 403: Forbidden" in error_message: raise ValueError("유튜브에서 다운로드를 차단했습니다 (오류 403). Secrets의 쿠키 정보가 유효한지 확인해주세요.")
                else: raise ValueError(f"다운로드 중 오류가 발생했습니다: {error_message}")
            except Exception as e:
                raise RuntimeError(f"알 수 없는 오류가 발생했습니다: {e}")

            downloaded_files = os.listdir(download_path)
            if not downloaded_files: raise FileNotFoundError("다운로드된 파일이 없습니다. URL을 다시 확인하거나, 재생목록의 모든 영상이 유효한지 확인해주세요.")
            
            zip_path = os.path.join(temp_dir, "playlist.zip")
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for file in downloaded_files:
                    zipf.write(os.path.join(download_path, file), arcname=file)
            
            with open(zip_path, "rb") as f:
                return f.read(), "playlist.zip", "application/zip"

def get_image_base64(image_path):
    """이미지 파일을 Base64로 인코딩하여 반환합니다."""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
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
    
    st.title("JY2mate")
    st.markdown("<p>유튜브 영상과 오디오를 간편하게 다운로드하세요.</p><br>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Developed by JunyoungCho</p>", unsafe_allow_html=True)

    if "YOUTUBE_COOKIES" not in st.secrets or not st.secrets["YOUTUBE_COOKIES"]:
        st.warning("⚠️ Secrets에 쿠키 정보(YOUTUBE_COOKIES)가 없습니다. 다운로드 실패 확률이 높습니다.")
    st.info(f"ℹ️ 현재 yt-dlp 버전: {yt_dlp.version.__version__}")

    url = st.text_input("다운로드할 YouTube URL을 입력하세요.", placeholder="https://www.youtube.com/watch?v=...")

    col1, col2 = st.columns([1, 2])
    with col1:
        # is_playlist = st.checkbox("재생목록 전체 다운로드")
        is_playlist = False  # << [수정 3] 재생목록 다운로드 옵션 제거
    with col2:
        download_type = st.radio("다운로드 타입", ('영상', '오디오'), horizontal=True, label_visibility="collapsed")

    col_quality, col_container = st.columns(2)
    with col_quality:
        if download_type == '영상':
            # quality = st.selectbox("화질 선택", ('best', '1080p', '720p', '480p'))
            quality = st.selectbox("화질 선택", ('1080p', '720p', '480p')) # << [수정 4] 'best' 옵션 제거
        else: # 오디오
            quality = st.selectbox("음질 선택 (kbps)", ('192', '320', '128'))
    with col_container:
        if download_type == '영상':
            container = st.selectbox("확장자 선택", ('mp4', 'mkv'))
        else: # 오디오
            container = st.selectbox("확장자 선택", ('mp3', 'flac', 'm4a', 'wav'))

    action_col1, action_col2 = st.columns(2)
    
    with action_col1:
        if st.button("다운로드 시작", use_container_width=True, type="primary"):
            if url:
                with st.spinner(f"다운로드를 시작합니다..."):
                    try:
                        file_data, display_name, mime_type = download_content(
                            url, download_type, quality, container, is_playlist
                        )
                        st.success(f"**{display_name}** 처리가 완료되었습니다!")
                        
                        # [수정 완료] mime=type -> mime=mime_type
                        st.download_button(
                            label=f"📥 '{display_name}' 다운로드",
                            data=file_data,
                            file_name=display_name,
                            mime=mime_type,
                            use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"오류: {e}", icon="🚨")
            else:
                st.warning("유튜브 URL을 입력해주세요.")

    with action_col2:
        if st.button("상세 정보 확인", use_container_width=True):
            if url:
                with st.spinner("유튜브로부터 상세 정보를 가져오는 중..."):
                    info = get_video_info(url)
                    if "error" in info:
                        st.error("정보를 가져오는 데 실패했습니다.")
                        with st.expander("에러 원문 보기"):
                            st.code(info["error"])
                    else:
                        title = info.get('title', '제목 없음')
                        st.success(f"**'{title}'** 의 정보를 성공적으로 가져왔습니다.")
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
            st.header("🔐 인증")
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
    st.info("👈 사이드바에서 인증 코드를 입력하여 앱 사용을 시작하세요.")