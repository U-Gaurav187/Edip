package com.pny.pdfeditor.data.api

import com.pny.pdfeditor.data.model.*
import okhttp3.MultipartBody
import okhttp3.ResponseBody
import retrofit2.http.*

interface PdfApiService {

    @Multipart
    @POST("documents/upload")
    suspend fun uploadDocument(
        @Part file: MultipartBody.Part
    ): DocumentInspectionResponse

    @GET("documents/{doc_id}/pages/{page_index}/inspect")
    suspend fun inspectPage(
        @Path("doc_id") docId: String,
        @Path("page_index") pageIndex: Int
    ): PageInspection

    @GET("documents/{doc_id}/pages/{page_index}/render")
    suspend fun renderPage(
        @Path("doc_id") docId: String,
        @Path("page_index") pageIndex: Int,
        @Query("dpi") dpi: Int = 150,
        @Query("t") timestamp: Long
    ): ResponseBody

    @POST("documents/{doc_id}/text/edit")
    suspend fun editText(
        @Path("doc_id") docId: String,
        @Body request: TextEditRequest
    ): PageInspection

    @POST("documents/{doc_id}/text/delete")
    suspend fun deleteText(
        @Path("doc_id") docId: String,
        @Body request: TextDeleteRequest
    ): PageInspection

    @POST("documents/{doc_id}/pages/rotate")
    suspend fun rotatePage(
        @Path("doc_id") docId: String,
        @Body request: PageRotateRequest
    ): OperationResult

    @POST("documents/{doc_id}/ocr")
    suspend fun runOcr(
        @Path("doc_id") docId: String,
        @Body request: OcrRequest
    ): OperationResult

    @Streaming
    @GET("documents/{doc_id}/export")
    suspend fun exportDocument(
        @Path("doc_id") docId: String,
        @Query("format") format: String = "pdf",
        @Query("t") timestamp: Long
    ): ResponseBody
}
