package com.pny.pdfeditor.data.model

import com.google.gson.annotations.SerializedName

data class DocumentMetadata(
    val title: String? = null,
    val author: String? = null,
    val subject: String? = null,
    val creator: String? = null,
    val producer: String? = null,
    val page_count: Int = 1
)

data class SpanDetail(
    val text: String,
    val bbox: List<Float>, // [x0, y0, x1, y1]
    var origin: List<Float>, // [x, y]
    val font: String,
    val size: Float,
    val color: Int = 0,
    val color_rgb: List<Float> = listOf(0f, 0f, 0f),
    val flags: Int = 0
) {
    val safeMinX: Float get() = bbox.getOrElse(0) { 0f }
    val safeMinY: Float get() = bbox.getOrElse(1) { 0f }
    val safeMaxX: Float get() = bbox.getOrElse(2) { safeMinX + 50f }
    val safeMaxY: Float get() = bbox.getOrElse(3) { safeMinY + 14f }

    val safeOriginX: Float get() = if (origin.size >= 2) origin[0] else minOf(safeMinX, safeMaxX)
    val safeOriginY: Float get() = if (origin.size >= 2) origin[1] else maxOf(safeMinY, safeMaxY)
}

data class LineDetail(
    val bbox: List<Float>,
    val spans: List<SpanDetail> = emptyList()
)

data class TextBlockDetail(
    val bbox: List<Float>,
    val lines: List<LineDetail> = emptyList()
)

data class ImageObjectDetail(
    val xref: Int,
    val bbox: List<Float>,
    val width: Int,
    val height: Int,
    val colorspace: String = ""
)

data class PageInspection(
    val page_index: Int,
    val width: Float,
    val height: Float,
    val rotation: Int = 0,
    val is_scanned: Boolean = false,
    val text_blocks: List<TextBlockDetail> = emptyList(),
    val images: List<ImageObjectDetail> = emptyList()
) {
    fun getSelectableSpans(isLineMode: Boolean = true): List<SpanDetail> {
        val rawLines = mutableListOf<SpanDetail>()
        for (block in text_blocks) {
            for (line in block.lines) {
                if (isLineMode) {
                    if (line.spans.isEmpty()) continue
                    val fullText = line.spans.joinToString("") { it.text }
                    if (fullText.isBlank()) continue

                    val prim = line.spans.firstOrNull { it.text.isNotBlank() } ?: line.spans.first()
                    val minX = if (line.bbox.size >= 4) line.bbox[0] else line.spans.minOf { it.safeMinX }
                    val minY = if (line.bbox.size >= 4) line.bbox[1] else line.spans.minOf { it.safeMinY }
                    val maxX = if (line.bbox.size >= 4) line.bbox[2] else line.spans.maxOf { it.safeMaxX }
                    val maxY = if (line.bbox.size >= 4) line.bbox[3] else line.spans.maxOf { it.safeMaxY }

                    val origX = if (prim.origin.size >= 2) prim.origin[0] else minX
                    val origY = if (prim.origin.size >= 2) prim.origin[1] else maxY

                    rawLines.add(
                        SpanDetail(
                            text = fullText,
                            bbox = listOf(minX, minY, maxX, maxY),
                            origin = listOf(origX, origY),
                            font = prim.font,
                            size = prim.size,
                            color = prim.color,
                            color_rgb = prim.color_rgb,
                            flags = prim.flags
                        )
                    )
                } else {
                    for (span in line.spans) {
                        if (span.text.isNotBlank()) {
                            rawLines.add(span)
                        }
                    }
                }
            }
        }

        if (!isLineMode || rawLines.isEmpty()) {
            return rawLines
        }

        // In Line Mode: sort lines by vertical position then horizontal position
        rawLines.sortWith(compareBy({ it.safeMinY }, { it.safeMinX }))

        // Merge collinear line fragments on the same baseline/row
        // (prevents split titles and orphan trailing letters like "I" / "- I" from being left behind un-redacted)
        val merged = mutableListOf<SpanDetail>()
        for (line in rawLines) {
            if (merged.isEmpty()) {
                merged.add(line)
                continue
            }
            val last = merged.last()
            val vOverlap = minOf(last.safeMaxY, line.safeMaxY) - maxOf(last.safeMinY, line.safeMinY)
            val minH = minOf(last.safeMaxY - last.safeMinY, line.safeMaxY - line.safeMinY)
            val horizontalGap = line.safeMinX - last.safeMaxX

            // Collinear condition: lines share same vertical row (overlap > 45% of line height)
            // and are separated by a reasonable gap (< 65pt) without jumping backwards
            if (minH > 0 && vOverlap >= minH * 0.45f && horizontalGap in -5f..65f) {
                val sep = if (last.text.endsWith(" ") || line.text.startsWith(" ")) "" else " "
                val combinedText = last.text.trimEnd() + sep + line.text.trimStart()
                val combinedBbox = listOf(
                    minOf(last.safeMinX, line.safeMinX),
                    minOf(last.safeMinY, line.safeMinY),
                    maxOf(last.safeMaxX, line.safeMaxX),
                    maxOf(last.safeMaxY, line.safeMaxY)
                )
                merged[merged.size - 1] = last.copy(
                    text = combinedText,
                    bbox = combinedBbox
                )
            } else {
                merged.add(line)
            }
        }
        return merged
    }
}

data class OcrRequest(
    val page_indices: List<Int>? = null,
    val language: String = "eng"
)

data class DocumentInspectionResponse(
    val document_id: String,
    val filename: String,
    val page_count: Int,
    val metadata: DocumentMetadata? = null,
    val pages: List<PageInspection> = emptyList()
)

data class TextEditRequest(
    val page_index: Int,
    val bbox: List<Float>,
    val origin: List<Float>,
    val new_text: String,
    val font_name: String,
    val font_size: Float,
    val color_rgb: List<Float>
)

data class TextDeleteRequest(
    val page_index: Int,
    val bbox: List<Float>
)

data class PageRotateRequest(
    val page_index: Int,
    val rotation_delta: Int = 90
)

data class OperationResult(
    val success: Boolean,
    val message: String,
    val document_id: String? = null
)
