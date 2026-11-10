"""Local-only extraction in a separate worker process, with bounded input duration."""
import json
import math
import os
from pathlib import Path
import sys
from functools import lru_cache


class ExtractionError(ValueError):
    pass


class NoRecognizedText(ExtractionError):
    pass


def media_duration(path):
    import av
    with av.open(str(path)) as container:
        if not container.streams.audio:
            raise ExtractionError('媒体没有音轨，请关联字幕或上传含音轨的版本')
        duration = float(container.duration / av.time_base) if container.duration else 0
        if not math.isfinite(duration) or duration <= 0:
            raise ExtractionError('无法确定媒体时长，请转码后上传')
        if duration > 3600:
            raise ExtractionError('媒体超过60分钟，请分段上传')
        return duration


@lru_cache(maxsize=1)
def ocr_engine():
    from rapidocr import RapidOCR
    return RapidOCR()


def ocr_image(image):
    result = ocr_engine()(image)
    texts = list(result.txts if result.txts is not None else [])
    scores = [float(score) for score in (result.scores if result.scores is not None else [])]
    if not texts:
        raise NoRecognizedText('未识别到文字，请上传清晰图片或补充正文')
    return '\n'.join(texts), min(scores) if scores else 0


def extract(path, operation):
    if operation == 'ocr':
        from PIL import Image
        if path.suffix.lower() == '.pdf':
            import pypdfium2
            document = pypdfium2.PdfDocument(str(path))
            if len(document) > 100:
                raise ExtractionError('扫描PDF最多100页，请拆分上传')
            parts, scores, unreadable = [], [], []
            try:
                for index in range(len(document)):
                    page = document[index]
                    width,height=page.get_size()
                    if width*height*2.25>25_000_000:
                        page.close()
                        raise ExtractionError('PDF页面尺寸过大，请缩小页面或拆分上传')
                    bitmap = page.render(scale=1.5)
                    try:
                        try:body, score = ocr_image(bitmap.to_pil())
                        except NoRecognizedText:
                            unreadable.append(index+1)
                            continue
                    finally:
                        bitmap.close()
                        page.close()
                    parts.append(f'【页码 {index + 1}】\n{body}')
                    scores.append(score)
            finally:
                document.close()
            if not parts:raise NoRecognizedText('PDF未识别到文字，请补充清晰扫描件或正文')
            return {'body': '\n\n'.join(parts), 'confidence': 0 if unreadable else min(scores), 'method': 'local_ocr', 'unreadable_pages':unreadable}
        Image.MAX_IMAGE_PIXELS = 25_000_000
        with Image.open(path) as image:
            image.load()
            body, score = ocr_image(image.convert('RGB'))
        return {'body': body, 'confidence': score, 'method': 'local_ocr'}
    if operation == 'transcribe':
        from faster_whisper import WhisperModel
        duration = media_duration(path)
        model_root=Path(os.getenv('ZHIXING_MODEL_DIR',str(Path(__file__).resolve().parents[2]/'data'/'models')))
        model_path = os.getenv('ZHIXING_WHISPER_MODEL', str(model_root/'whisper-tiny'))
        if not model_path:
            raise ExtractionError('尚未配置本地转写模型，请设置ZHIXING_WHISPER_MODEL')
        model = WhisperModel(model_path, device='cpu', compute_type='int8', cpu_threads=2,
                             local_files_only=True)
        segments, _ = model.transcribe(str(path), beam_size=3, vad_filter=True)
        parts, scores = [], []
        for segment in segments:
            if segment.no_speech_prob > .6 or not segment.text.strip():
                continue
            parts.append(f'【时间 {segment.start:g}–{segment.end:g} 秒】\n{segment.text.strip()}')
            scores.append(math.exp(min(0, segment.avg_logprob)))
        if not parts:
            raise ExtractionError('未识别到有效语音，请关联人工字幕')
        return {'body': '\n\n'.join(parts), 'confidence': min(scores),
                'duration_seconds': duration, 'method': 'local_whisper',
                'confidence_kind': 'sequence_probability_proxy'}
    raise ExtractionError('处理操作不支持')


if __name__ == '__main__':
    output = Path(sys.argv[3])
    try:
        result = extract(Path(sys.argv[1]), sys.argv[2])
    except ImportError:
        result = {'error': '本地处理依赖未安装，请按媒体依赖清单安装'}
    except ExtractionError as error:
        result = {'error': str(error)[:300]}
    except Exception:
        result = {'error': '本地识别失败，请检查文件格式、模型和依赖'}
    output.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
