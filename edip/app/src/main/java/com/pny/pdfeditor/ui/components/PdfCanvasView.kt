package com.pny.pdfeditor.ui.components

import android.graphics.Bitmap
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.calculateCentroid
import androidx.compose.foundation.gestures.calculatePan
import androidx.compose.foundation.gestures.calculateZoom
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CenterFocusWeak
import androidx.compose.material.icons.filled.OpenWith
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.pny.pdfeditor.data.model.PageInspection
import com.pny.pdfeditor.data.model.SpanDetail
import com.pny.pdfeditor.ui.theme.*
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

@Composable
fun PdfCanvasView(
    pageBitmap: Bitmap?,
    pageInfo: PageInspection?,
    selectedSpan: SpanDetail?,
    dragOffset: Offset, // In PDF points
    isDragMode: Boolean,
    isLineMode: Boolean = true,
    onSpanSelected: (SpanDetail) -> Unit,
    onDragDelta: (Float, Float) -> Unit, // (pdfDeltaX, pdfDeltaY)
    modifier: Modifier = Modifier
) {
    var scale by remember { mutableFloatStateOf(1f) }
    var offset by remember { mutableStateOf(Offset.Zero) }

    val selectableSpans = remember(pageInfo, isLineMode) {
        pageInfo?.getSelectableSpans(isLineMode) ?: emptyList()
    }

    Box(
        modifier = modifier
            .fillMaxSize()
            .background(DarkBackground)
    ) {
        Canvas(
            modifier = Modifier
                .fillMaxSize()
                .pointerInput(selectableSpans, pageBitmap, isDragMode, selectedSpan) {
                    awaitEachGesture {
                        val down = awaitFirstDown(requireUnconsumed = false)
                        val startTime = System.currentTimeMillis()
                        val startPos = down.position
                        var isMultiTouch = false
                        var totalPan = Offset.Zero
                        val touchSlop = viewConfiguration.touchSlop
                        var lastPos = startPos

                        do {
                            val event = awaitPointerEvent()
                            val count = event.changes.size

                            if (count >= 2) {
                                isMultiTouch = true
                                val zoomChange = event.calculateZoom()
                                val panChange = event.calculatePan()
                                val centroid = event.calculateCentroid()

                                val oldScale = scale
                                val newScale = (scale * zoomChange).coerceIn(0.6f, 8.0f)
                                val scaleFactor = if (oldScale > 0) newScale / oldScale else 1f

                                scale = newScale
                                offset = (offset - centroid) * scaleFactor + centroid + panChange

                                event.changes.forEach { it.consume() }
                            } else if (count == 1 && !isMultiTouch) {
                                val currPos = event.changes[0].position
                                val deltaScreen = currPos - lastPos
                                totalPan += deltaScreen

                                if (totalPan.getDistance() > touchSlop) {
                                    if (isDragMode && selectedSpan != null && pageInfo != null && pageBitmap != null) {
                                        val canvasW = size.width.toFloat()
                                        val canvasH = size.height.toFloat()
                                        val imgW = pageBitmap.width.toFloat()
                                        val imgH = pageBitmap.height.toFloat()

                                        if (canvasW > 0 && canvasH > 0 && imgW > 0 && imgH > 0 && pageInfo.width > 0 && pageInfo.height > 0) {
                                            val baseScale = min(canvasW / imgW, canvasH / imgH)
                                            val displayW = imgW * baseScale * scale
                                            val displayH = imgH * baseScale * scale

                                            val pointScaleX = displayW / pageInfo.width
                                            val pointScaleY = displayH / pageInfo.height

                                            if (pointScaleX > 0 && pointScaleY > 0) {
                                                val pdfDeltaX = deltaScreen.x / pointScaleX
                                                val pdfDeltaY = deltaScreen.y / pointScaleY
                                                onDragDelta(pdfDeltaX, pdfDeltaY)
                                            }
                                        }
                                    } else {
                                        // Smooth 1-finger panning across the canvas
                                        offset += deltaScreen
                                    }
                                    event.changes[0].consume()
                                }
                                lastPos = currPos
                            }
                        } while (event.changes.any { it.pressed })

                        val elapsed = System.currentTimeMillis() - startTime

                        // Single Tap Detection:
                        // 1 finger, no multi-touch, moved less than touchSlop * 2, finished within 500ms
                        if (!isMultiTouch && totalPan.getDistance() < touchSlop * 2f && elapsed < 500) {
                            if (pageInfo != null && pageBitmap != null && selectableSpans.isNotEmpty()) {
                                val canvasW = size.width.toFloat()
                                val canvasH = size.height.toFloat()

                                val imgW = pageBitmap.width.toFloat()
                                val imgH = pageBitmap.height.toFloat()

                                if (canvasW > 0 && canvasH > 0 && imgW > 0 && imgH > 0 && pageInfo.width > 0 && pageInfo.height > 0) {
                                    val baseScale = min(canvasW / imgW, canvasH / imgH)
                                    val displayW = imgW * baseScale * scale
                                    val displayH = imgH * baseScale * scale

                                    val leftEdge = (canvasW - displayW) / 2f + offset.x
                                    val topEdge = (canvasH - displayH) / 2f + offset.y

                                    val pointScaleX = displayW / pageInfo.width
                                    val pointScaleY = displayH / pageInfo.height

                                    var bestSpan: SpanDetail? = null
                                    var bestDist = Float.MAX_VALUE

                                    for (span in selectableSpans) {
                                        if (span.text.isBlank()) continue

                                        val minX = span.safeMinX
                                        val maxX = span.safeMaxX
                                        val minY = span.safeMinY
                                        val maxY = span.safeMaxY

                                        // Screen bounding box with minimum effective touch area (at least 32x26 pixels)
                                        val minTouchW = 32f
                                        val minTouchH = 26f
                                        val rawW = (maxX - minX) * pointScaleX
                                        val rawH = (maxY - minY) * pointScaleY
                                        val touchW = max(rawW, minTouchW)
                                        val touchH = max(rawH, minTouchH)
                                        val centerX = leftEdge + ((minX + maxX) / 2f) * pointScaleX
                                        val centerY = topEdge + ((minY + maxY) / 2f) * pointScaleY
                                        val sx0 = centerX - touchW / 2f
                                        val sx1 = centerX + touchW / 2f
                                        val sy0 = centerY - touchH / 2f
                                        val sy1 = centerY + touchH / 2f

                                        // Distance from tap position to bounding box
                                        val dx = max(0f, max(sx0 - startPos.x, startPos.x - sx1))
                                        val dy = max(0f, max(sy0 - startPos.y, startPos.y - sy1))
                                        val dist = sqrt(dx * dx + dy * dy)

                                        if (dist < bestDist) {
                                            bestDist = dist
                                            bestSpan = span
                                        }
                                    }

                                    // Generous hit threshold: 140 pixels radius around touch point
                                    if (bestSpan != null && bestDist <= 140f) {
                                        onSpanSelected(bestSpan)
                                    }
                                }
                            }
                        }
                    }
                }
        ) {
            if (pageBitmap == null || pageInfo == null) return@Canvas

            val canvasW = size.width
            val canvasH = size.height

            val imgW = pageBitmap.width.toFloat()
            val imgH = pageBitmap.height.toFloat()

            val baseScale = min(canvasW / imgW, canvasH / imgH)
            val displayW = imgW * baseScale * scale
            val displayH = imgH * baseScale * scale

            val leftEdge = (canvasW - displayW) / 2f + offset.x
            val topEdge = (canvasH - displayH) / 2f + offset.y

            // 1. Draw Rendered Document Bitmap
            drawImage(
                image = pageBitmap.asImageBitmap(),
                dstOffset = IntOffset(leftEdge.toInt(), topEdge.toInt()),
                dstSize = IntSize(displayW.toInt(), displayH.toInt())
            )

            // 2. Draw Interactive Bounding Boxes for Text Objects (Lines or Words)
            val pointScaleX = (displayW / pageInfo.width)
            val pointScaleY = (displayH / pageInfo.height)

            for (span in selectableSpans) {
                if (span.text.isBlank()) continue
                val isSelected = (span.bbox == selectedSpan?.bbox || span == selectedSpan)
                val extraX = if (isSelected) dragOffset.x else 0f
                val extraY = if (isSelected) dragOffset.y else 0f

                val minX = span.safeMinX
                val maxX = span.safeMaxX
                val minY = span.safeMinY
                val maxY = span.safeMaxY

                val rawW = (maxX - minX) * pointScaleX
                val rawH = (maxY - minY) * pointScaleY
                val rw = max(18f, rawW)
                val rh = max(14f, rawH)
                val rx0 = leftEdge + (minX + extraX) * pointScaleX - (if (rawW < 18f) (18f - rawW) / 2f else 0f)
                val ry0 = topEdge + (minY + extraY) * pointScaleY - (if (rawH < 14f) (14f - rawH) / 2f else 0f)

                if (isSelected) {
                    // Selected text box highlight
                    drawRect(
                        color = HotspotSelected,
                        topLeft = Offset(rx0, ry0),
                        size = Size(rw, rh)
                    )
                    drawRect(
                        color = AccentBlue,
                        topLeft = Offset(rx0, ry0),
                        size = Size(rw, rh),
                        style = Stroke(width = 3.5f)
                    )
                } else {
                    // Non-selected text bounding box
                    drawRect(
                        color = AccentBlue.copy(alpha = 0.10f),
                        topLeft = Offset(rx0, ry0),
                        size = Size(rw, rh)
                    )
                    drawRect(
                        color = AccentBlue.copy(alpha = 0.45f),
                        topLeft = Offset(rx0, ry0),
                        size = Size(rw, rh),
                        style = Stroke(width = 1.2f)
                    )
                }
            }
        }

        // Overlay: Drag Mode Indicator Banner
        if (isDragMode && selectedSpan != null) {
            Surface(
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .padding(top = 12.dp),
                shape = RoundedCornerShape(20.dp),
                color = AccentBlue,
                shadowElevation = 8.dp
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Icon(
                        Icons.Default.OpenWith,
                        contentDescription = null,
                        tint = Color.White,
                        modifier = Modifier.size(18.dp)
                    )
                    Text(
                        text = "Drag Mode Active: Drag box with 1 finger",
                        color = Color.White,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }

        // Overlay: Zoom Level & Reset Control
        if (scale != 1f || offset != Offset.Zero) {
            Surface(
                modifier = Modifier
                    .align(Alignment.BottomEnd)
                    .padding(16.dp),
                shape = RoundedCornerShape(16.dp),
                color = DarkSurface.copy(alpha = 0.9f),
                shadowElevation = 6.dp
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Text(
                        text = "${(scale * 100).toInt()}%",
                        color = TextPrimary,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold
                    )
                    IconButton(
                        onClick = {
                            scale = 1f
                            offset = Offset.Zero
                        },
                        modifier = Modifier.size(28.dp)
                    ) {
                        Icon(
                            Icons.Default.CenterFocusWeak,
                            contentDescription = "Reset Zoom",
                            tint = AccentBlueLight
                        )
                    }
                }
            }
        }
    }
}
