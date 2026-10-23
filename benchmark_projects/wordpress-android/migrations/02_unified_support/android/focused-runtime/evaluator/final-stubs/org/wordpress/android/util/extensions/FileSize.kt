package org.wordpress.android.util.extensions

import android.app.Application
import android.net.Uri
import evaluator.support.leaf.EvaluatorLeaf

fun Uri.fileSize(application: Application): Long = EvaluatorLeaf.uriSizes[toString()] ?: 0L
