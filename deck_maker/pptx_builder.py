"""Pure-Python OpenXML PowerPoint (.pptx) builder."""

from __future__ import annotations

from http import HTTPStatus
import io
import zipfile

from deck_maker.config import MAX_SLIDES
from deck_maker.exceptions import AppError


def png_dimensions(image: bytes) -> tuple[int, int]:
    """Extract width and height in pixels from PNG IHDR chunk."""
    if (
        len(image) < 24
        or not image.startswith(b"\x89PNG\r\n\x1a\n")
        or not all((int.from_bytes(image[16:20], "big"), int.from_bytes(image[20:24], "big")))
    ):
        raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "PDF rendering did not produce PNG images.")
    return int.from_bytes(image[16:20], "big"), int.from_bytes(image[20:24], "big")


def content_types(slide_count: int) -> str:
    """Generate [Content_Types].xml manifest for PPTX archive."""
    slides = "".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" '
        f'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, slide_count + 1)
    )
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        f'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        f'<Default Extension="xml" ContentType="application/xml"/>'
        f'<Default Extension="png" ContentType="image/png"/>'
        f'<Override PartName="/ppt/presentation.xml" '
        f'ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
        f'<Override PartName="/ppt/slideMasters/slideMaster1.xml" '
        f'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
        f'<Override PartName="/ppt/slideLayouts/slideLayout1.xml" '
        f'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
        f"{slides}</Types>"
    )


def pptx_from_images(images: list[bytes]) -> bytes:
    """Assemble a standard OpenXML PPTX presentation embedding each PNG as a slide."""
    if not 1 <= len(images) <= MAX_SLIDES:
        raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, f"The PDF must contain 1 to {MAX_SLIDES} pages.")

    width, height = png_dimensions(images[0])
    slide_width = 12_192_000 if width >= height else round(12_192_000 * width / height)
    slide_height = round(12_192_000 * height / width) if width >= height else 12_192_000

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types(len(images)))
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="ppt/presentation.xml"/>'
            "</Relationships>",
        )
        ids = "".join(f'<p:sldId id="{255 + number}" r:id="rId{number + 1}"/>' for number in range(1, len(images) + 1))
        archive.writestr(
            "ppt/presentation.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
            f'<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
            f"<p:sldIdLst>{ids}</p:sldIdLst>"
            f'<p:sldSz cx="{slide_width}" cy="{slide_height}" type="custom"/>'
            f'<p:notesSz cx="6858000" cy="9144000"/></p:presentation>',
        )
        relationships = "".join(
            f'<Relationship Id="rId{number + 1}" '
            f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
            f'Target="slides/slide{number}.xml"/>'
            for number in range(1, len(images) + 1)
        )
        archive.writestr(
            "ppt/_rels/presentation.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" '
            'Target="slideMasters/slideMaster1.xml"/>'
            f"{relationships}</Relationships>",
        )
        archive.writestr(
            "ppt/slideMasters/slideMaster1.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
            '<p:cSld name=""><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/>'
            "</p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld>"
            '<p:clrMap accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" '
            'accent5="accent5" accent6="accent6" bg1="lt1" bg2="lt2" folHlink="folHlink" hlink="hlink" '
            'tx1="dk1" tx2="dk2"/>'
            '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
            "<p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>",
        )
        archive.writestr(
            "ppt/slideMasters/_rels/slideMaster1.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" '
            'Target="../slideLayouts/slideLayout1.xml"/></Relationships>',
        )
        archive.writestr(
            "ppt/slideLayouts/slideLayout1.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">'
            '<p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/>'
            "</p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld></p:sldLayout>",
        )
        archive.writestr(
            "ppt/slideLayouts/_rels/slideLayout1.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" '
            'Target="../slideMasters/slideMaster1.xml"/></Relationships>',
        )
        for index, image in enumerate(images, 1):
            image_width, image_height = png_dimensions(image)
            w = slide_width
            h = round(w * image_height / image_width)
            if h > slide_height:
                h = slide_height
                w = round(h * image_width / image_height)
            x, y = (slide_width - w) // 2, (slide_height - h) // 2
            slide = (
                f'<?xml version="1.0" encoding="UTF-8"?>'
                f'<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
                f'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
                f'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
                f'<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/>'
                f"</p:nvGrpSpPr><p:grpSpPr/>"
                f"<p:pic><p:nvPicPr>"
                f'<p:cNvPr id="2" name="Slide {index}"/><p:cNvPicPr/><p:nvPr/>'
                f"</p:nvPicPr>"
                f'<p:blipFill><a:blip r:embed="rId1"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
                f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>'
                f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
                f"</p:spTree></p:cSld>"
                f"<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>"
            )
            archive.writestr(f"ppt/slides/slide{index}.xml", slide)
            archive.writestr(
                f"ppt/slides/_rels/slide{index}.xml.rels",
                f'<?xml version="1.0" encoding="UTF-8"?>'
                f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                f'<Relationship Id="rId1" '
                f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                f'Target="../media/image{index}.png"/>'
                f'<Relationship Id="rId2" '
                f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" '
                f'Target="../slideLayouts/slideLayout1.xml"/></Relationships>',
            )
            archive.writestr(f"ppt/media/image{index}.png", image)

    return buffer.getvalue()
