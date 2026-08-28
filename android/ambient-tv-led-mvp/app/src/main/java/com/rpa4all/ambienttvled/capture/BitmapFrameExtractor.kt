package com.rpa4all.ambienttvled.capture

import android.graphics.Bitmap
import android.media.Image
import com.rpa4all.ambienttvled.model.FrameSample

object BitmapFrameExtractor {
    fun extract(image: Image, targetWidth: Int, targetHeight: Int): FrameSample {
        val plane = image.planes.first()
        val buffer = plane.buffer
        val pixelStride = plane.pixelStride
        val rowStride = plane.rowStride
        val rowPadding = rowStride - pixelStride * image.width

        val bitmap = Bitmap.createBitmap(
            image.width + rowPadding / pixelStride,
            image.height,
            Bitmap.Config.ARGB_8888,
        )
        bitmap.copyPixelsFromBuffer(buffer)

        val cropped = Bitmap.createBitmap(bitmap, 0, 0, image.width, image.height)
        bitmap.recycle()

        val scaled = if (cropped.width != targetWidth || cropped.height != targetHeight) {
            Bitmap.createScaledBitmap(cropped, targetWidth, targetHeight, true)
        } else {
            cropped
        }

        if (scaled !== cropped) {
            cropped.recycle()
        }

        val pixels = IntArray(targetWidth * targetHeight)
        scaled.getPixels(pixels, 0, targetWidth, 0, 0, targetWidth, targetHeight)
        scaled.recycle()

        return FrameSample(
            width = targetWidth,
            height = targetHeight,
            pixels = pixels,
        )
    }
}
