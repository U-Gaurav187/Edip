package com.pny.pdfeditor.ui

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.compose.ui.geometry.Offset
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pny.pdfeditor.data.api.ApiClient
import com.pny.pdfeditor.data.model.OcrRequest
import com.pny.pdfeditor.data.model.PageInspection
import com.pny.pdfeditor.data.model.PageRotateRequest
import com.pny.pdfeditor.data.model.SpanDetail
import com.pny.pdfeditor.data.model.TextDeleteRequest
import com.pny.pdfeditor.data.model.TextEditRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File
import java.io.FileOutputStream

class MainViewModel : ViewModel() {

    private val api = ApiClient.apiService

    private val _currentDocId = MutableStateFlow<String?>(null)
    val currentDocId: StateFlow<String?> = _currentDocId.asStateFlow()

    private val _docName = MutableStateFlow("Edip PDF Studio")
    val docName: StateFlow<String> = _docName.asStateFlow()

    private val _pageCount = MutableStateFlow(0)
    val pageCount: StateFlow<Int> = _pageCount.asStateFlow()

    private val _currentPageIndex = MutableStateFlow(0)
    val currentPageIndex: StateFlow<Int> = _currentPageIndex.asStateFlow()

    private val _currentPageInfo = MutableStateFlow<PageInspection?>(null)
    val currentPageInfo: StateFlow<PageInspection?> = _currentPageInfo.asStateFlow()

    private val _pageBitmap = MutableStateFlow<Bitmap?>(null)
    val pageBitmap: StateFlow<Bitmap?> = _pageBitmap.asStateFlow()

    private val _selectedSpan = MutableStateFlow<SpanDetail?>(null)
    val selectedSpan: StateFlow<SpanDetail?> = _selectedSpan.asStateFlow()

    private val _dragOffset = MutableStateFlow(Offset.Zero) // In PDF Points
    val dragOffset: StateFlow<Offset> = _dragOffset.asStateFlow()

    private val _isDragMode = MutableStateFlow(false)
    val isDragMode: StateFlow<Boolean> = _isDragMode.asStateFlow()

    private val _isLineMode = MutableStateFlow(true) // Line Mode enabled by default for clean line boxes
    val isLineMode: StateFlow<Boolean> = _isLineMode.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _statusMessage = MutableStateFlow<String?>(null)
    val statusMessage: StateFlow<String?> = _statusMessage.asStateFlow()

    fun setDragMode(enabled: Boolean) {
        _isDragMode.value = enabled
    }

    fun setLineMode(enabled: Boolean) {
        _isLineMode.value = enabled
    }

    fun addDragDelta(dx: Float, dy: Float) {
        _dragOffset.value += Offset(dx, dy)
    }

    fun selectSpan(span: SpanDetail?) {
        _selectedSpan.value = span
        _dragOffset.value = Offset.Zero
        _isDragMode.value = false
    }

    fun clearStatusMessage() {
        _statusMessage.value = null
    }

    fun uploadPdf(context: Context, uri: Uri) {
        viewModelScope.launch {
            _isLoading.value = true
            _statusMessage.value = "Uploading PDF to cloud engine..."
            try {
                val bytes = withContext(Dispatchers.IO) {
                    context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
                } ?: throw Exception("Failed to read file from storage")

                val requestFile = bytes.toRequestBody("application/pdf".toMediaTypeOrNull())
                val body = MultipartBody.Part.createFormData("file", "document.pdf", requestFile)

                val response = withContext(Dispatchers.IO) {
                    api.uploadDocument(body)
                }

                _currentDocId.value = response.document_id
                _docName.value = response.filename
                _pageCount.value = response.page_count
                _currentPageIndex.value = 0

                loadCurrentPage()
                _statusMessage.value = "PDF loaded successfully!"
            } catch (e: Exception) {
                _statusMessage.value = "Upload error: ${e.localizedMessage}"
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun changePage(index: Int) {
        if (index in 0 until _pageCount.value) {
            _currentPageIndex.value = index
            selectSpan(null)
            loadCurrentPage()
        }
    }

    fun rotateCurrentPage() {
        val docId = _currentDocId.value ?: return
        val pIdx = _currentPageIndex.value

        viewModelScope.launch {
            _isLoading.value = true
            try {
                withContext(Dispatchers.IO) {
                    api.rotatePage(docId, PageRotateRequest(page_index = pIdx, rotation_delta = 90))
                }
                loadCurrentPage()
            } catch (e: Exception) {
                _statusMessage.value = "Rotate error: ${e.localizedMessage}"
            } finally {
                _isLoading.value = false
            }
        }
    }

    private suspend fun loadPageInternal(docId: String, pIdx: Int) {
        val (info, imgBytes) = withContext(Dispatchers.IO) {
            val pageInfo = api.inspectPage(docId, pIdx)
            val responseBody = api.renderPage(docId, pIdx, dpi = 150, timestamp = System.currentTimeMillis())
            Pair(pageInfo, responseBody.bytes())
        }

        if (imgBytes.isNotEmpty()) {
            val newBmp = BitmapFactory.decodeByteArray(imgBytes, 0, imgBytes.size)
            if (newBmp != null) {
                val oldBmp = _pageBitmap.value
                _currentPageInfo.value = info
                _pageBitmap.value = newBmp
                if (oldBmp != null && !oldBmp.isRecycled && oldBmp != newBmp) {
                    oldBmp.recycle()
                }
            }
        }
    }

    fun loadCurrentPage() {
        val docId = _currentDocId.value ?: return
        val pIdx = _currentPageIndex.value

        viewModelScope.launch {
            _isLoading.value = true
            try {
                loadPageInternal(docId, pIdx)
            } catch (e: Exception) {
                _statusMessage.value = "Page render error: ${e.localizedMessage}"
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun applyTextEdit(newText: String, fontName: String, fontSize: Float, colorRgb: List<Float>) {
        val docId = _currentDocId.value ?: return
        val span = _selectedSpan.value ?: return
        val pIdx = _currentPageIndex.value

        val shiftedOrigin = listOf(
            span.safeOriginX + _dragOffset.value.x,
            span.safeOriginY + _dragOffset.value.y
        )
        val bbox = listOf(span.safeMinX, span.safeMinY, span.safeMaxX, span.safeMaxY)

        viewModelScope.launch {
            _isLoading.value = true
            _statusMessage.value = "Applying PDF text edit..."
            try {
                val req = TextEditRequest(
                    page_index = pIdx,
                    bbox = bbox,
                    origin = shiftedOrigin,
                    new_text = newText,
                    font_name = fontName,
                    font_size = fontSize,
                    color_rgb = colorRgb
                )

                withContext(Dispatchers.IO) {
                    api.editText(docId, req)
                }

                selectSpan(null)
                loadPageInternal(docId, pIdx)
                _statusMessage.value = "Text edit applied!"
            } catch (e: Exception) {
                _statusMessage.value = "Edit failed: ${e.localizedMessage}"
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun addNewText(text: String, x: Float, y: Float, fontName: String, fontSize: Float, colorRgb: List<Float>) {
        val docId = _currentDocId.value ?: return
        val pIdx = _currentPageIndex.value

        viewModelScope.launch {
            _isLoading.value = true
            _statusMessage.value = "Adding new text..."
            try {
                val req = TextEditRequest(
                    page_index = pIdx,
                    bbox = listOf(x, y, x + 120f, y + fontSize + 4f),
                    origin = listOf(x, y + fontSize),
                    new_text = text,
                    font_name = fontName,
                    font_size = fontSize,
                    color_rgb = colorRgb
                )

                withContext(Dispatchers.IO) {
                    api.editText(docId, req)
                }

                selectSpan(null)
                loadPageInternal(docId, pIdx)
                _statusMessage.value = "New text added to PDF!"
            } catch (e: Exception) {
                _statusMessage.value = "Add text failed: ${e.localizedMessage}"
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun deleteSelectedText() {
        val docId = _currentDocId.value ?: return
        val span = _selectedSpan.value ?: return
        val pIdx = _currentPageIndex.value
        val bbox = listOf(span.safeMinX, span.safeMinY, span.safeMaxX, span.safeMaxY)

        viewModelScope.launch {
            _isLoading.value = true
            _statusMessage.value = "Deleting text..."
            try {
                withContext(Dispatchers.IO) {
                    api.deleteText(docId, TextDeleteRequest(page_index = pIdx, bbox = bbox))
                }
                selectSpan(null)
                loadPageInternal(docId, pIdx)
                _statusMessage.value = "Text deleted!"
            } catch (e: Exception) {
                _statusMessage.value = "Delete failed: ${e.localizedMessage}"
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun deleteSpan(span: SpanDetail) {
        val docId = _currentDocId.value ?: return
        val pIdx = _currentPageIndex.value
        val bbox = listOf(span.safeMinX, span.safeMinY, span.safeMaxX, span.safeMaxY)

        viewModelScope.launch {
            _isLoading.value = true
            _statusMessage.value = "Deleting text..."
            try {
                withContext(Dispatchers.IO) {
                    api.deleteText(docId, TextDeleteRequest(page_index = pIdx, bbox = bbox))
                }
                if (_selectedSpan.value?.bbox == span.bbox) {
                    selectSpan(null)
                }
                loadPageInternal(docId, pIdx)
                _statusMessage.value = "Text deleted!"
            } catch (e: Exception) {
                _statusMessage.value = "Delete failed: ${e.localizedMessage}"
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun runOcr(pageIndex: Int? = null) {
        val docId = _currentDocId.value ?: return
        val pIdx = pageIndex ?: _currentPageIndex.value

        viewModelScope.launch {
            _isLoading.value = true
            _statusMessage.value = "Running OCR scan to convert document to editable text..."
            try {
                withContext(Dispatchers.IO) {
                    api.runOcr(docId, OcrRequest(page_indices = listOf(pIdx)))
                }
                loadPageInternal(docId, pIdx)
                val totalSpans = _currentPageInfo.value?.text_blocks?.sumOf { b -> b.lines.sumOf { l -> l.spans.size } } ?: 0
                _statusMessage.value = "OCR Complete! $totalSpans text items recognized and ready to edit."
            } catch (e: Exception) {
                _statusMessage.value = "OCR failed: ${e.localizedMessage}"
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun exportPdf(context: Context, onSaved: (File) -> Unit) {
        val docId = _currentDocId.value ?: return

        viewModelScope.launch {
            _isLoading.value = true
            _statusMessage.value = "Exporting clean PDF..."
            try {
                val bytes = withContext(Dispatchers.IO) {
                    api.exportDocument(docId, format = "pdf", timestamp = System.currentTimeMillis()).bytes()
                }

                val timestamp = System.currentTimeMillis()
                val filename = "Edip_edited_$timestamp.pdf"

                val outFile = File(context.cacheDir, filename)
                withContext(Dispatchers.IO) {
                    FileOutputStream(outFile).use { it.write(bytes) }
                }

                withContext(Dispatchers.IO) {
                    try {
                        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.Q) {
                            val values = android.content.ContentValues().apply {
                                put(android.provider.MediaStore.MediaColumns.DISPLAY_NAME, filename)
                                put(android.provider.MediaStore.MediaColumns.MIME_TYPE, "application/pdf")
                                put(android.provider.MediaStore.MediaColumns.RELATIVE_PATH, android.os.Environment.DIRECTORY_DOWNLOADS)
                            }
                            val resolver = context.contentResolver
                            val uri = resolver.insert(android.provider.MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
                            uri?.let { destUri ->
                                resolver.openOutputStream(destUri)?.use { it.write(bytes) }
                            }
                        } else {
                            val dlDir = android.os.Environment.getExternalStoragePublicDirectory(android.os.Environment.DIRECTORY_DOWNLOADS)
                            val destFile = File(dlDir, filename)
                            FileOutputStream(destFile).use { it.write(bytes) }
                        }
                    } catch (e: Exception) {
                        // ignore public downloads failure
                    }
                }

                _statusMessage.value = "PDF exported to Downloads & ready to share!"
                onSaved(outFile)
            } catch (e: Exception) {
                _statusMessage.value = "Export error: ${e.localizedMessage}"
            } finally {
                _isLoading.value = false
            }
        }
    }
}
