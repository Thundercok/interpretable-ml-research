"""Unit tests for RAT image drop & clipboard ingress (Roadmap step 2.4)."""
from pathlib import Path
import pytest
from PyQt6.QtCore import QMimeData, QUrl
from PyQt6.QtGui import QGuiApplication, QImage

from rat.kernel.input_context import ImageInput
from rat.ui.image_input import (
    encode_image,
    image_from_bytes,
    image_from_mime,
    image_from_url,
    parse_pasted_mime_content,
)
from rat.ui.image_preview import ImagePreviewProvider
from rat.ui.mini_quick_controller import MiniQuickController


@pytest.fixture(scope="session")
def qapp():
    return QGuiApplication.instance() or QGuiApplication([])


def test_encode_and_read_image(tmp_path, qapp):
    img = QImage(64, 64, QImage.Format.Format_RGB32)
    img.fill(0xFF0000)
    img_input = encode_image(img, origin="dropped_image")
    assert isinstance(img_input, ImageInput)
    assert img_input.origin == "dropped_image"
    assert len(img_input.content) > 0
    assert img_input.content_sha256

    # From bytes
    from_b = image_from_bytes(img_input.content, origin="clipboard_image")
    assert from_b.origin == "clipboard_image"
    assert from_b.content_sha256 == img_input.content_sha256

    # From URL / file
    file_path = tmp_path / "test_sample.png"
    assert img.save(str(file_path), "PNG")
    from_url, name = image_from_url(QUrl.fromLocalFile(str(file_path)))
    assert name == "test_sample.png"
    assert from_url.origin == "dropped_file"
    assert from_url.source_file_sha256


def test_image_from_mime(tmp_path, qapp):
    img = QImage(32, 32, QImage.Format.Format_RGB32)
    img.fill(0x00FF00)
    mime = QMimeData()
    mime.setImageData(img)

    inp, label = image_from_mime(mime, clipboard=True)
    assert inp.origin == "clipboard_image"
    assert label == "Ảnh vừa dán"

    parsed = parse_pasted_mime_content(mime)
    assert parsed["kind"] == "image"
    assert parsed["image"].origin == "clipboard_image"


def test_image_preview_provider(qapp):
    img = QImage(40, 40, QImage.Format.Format_RGB32)
    img.fill(0x0000FF)
    inp = encode_image(img)

    provider = ImagePreviewProvider()
    url = provider.set_input(inp)
    assert url.startswith("image://mini-input/img-")

    retrieved, size = provider.requestImage(inp.input_id, None)
    assert not retrieved.isNull()
    assert size.width() > 0


@pytest.mark.unlaunched_surface
def test_controller_image_drop_handling(tmp_path, monkeypatch, qapp):
    """Mini desk image drops: a preview and a queued OCR-and-translate job.

    This covers an UNLAUNCHED surface. Nothing starts rat/ui/mini_quick.py (not the router, not
    pyproject, not packaging), and the main desk that users get sends every dropped file to
    openPdfDocument(), which rejects anything that is not a PDF. So this test proves the Mini
    controller works, not that a user can drop an image today. Wiring image drops into the main
    desk is open work; when it lands, add a test against QuickPDFController and retire this marker.
    """
    controller = MiniQuickController()
    assert not controller.snapshot["dropActive"]

    controller.setDropActive(True)
    assert controller.snapshot["dropActive"]

    controller.setDropActive(False)
    assert not controller.snapshot["dropActive"]

    img = QImage(30, 30, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFF)
    path = tmp_path / "diagram.png"
    img.save(str(path), "PNG")

    queued = []
    monkeypatch.setattr(controller, "enqueue", lambda kind, payload, *rest: queued.append((kind, payload)))

    assert controller.dropImage([QUrl.fromLocalFile(str(path))]) is True

    assert len(queued) == 1
    kind, payload = queued[0]
    assert kind == "capture_translate"
    assert payload["mode"] == "image"
    assert isinstance(payload["image_input"], ImageInput)
    assert controller.snapshot["imageLabel"]
    assert controller.snapshot["imagePreviewUrl"].startswith("image://mini-input/")

    controller.quit()
