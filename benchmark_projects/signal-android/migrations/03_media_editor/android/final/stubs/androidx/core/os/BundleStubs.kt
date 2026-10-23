package androidx.core.os

import android.os.Bundle
import android.os.Parcelable

fun bundleOf(vararg pairs: Pair<String, Any?>): Bundle = Bundle().also { bundle ->
  pairs.forEach { (key, value) -> if (value is Parcelable) bundle.putParcelable(key, value) }
}
