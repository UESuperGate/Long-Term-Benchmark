package org.signal.core.models.parcelers

import android.os.Parcel
import kotlinx.parcelize.Parceler

object NullableCharSequenceParceler : Parceler<CharSequence?> {
  override fun create(parcel: Parcel): CharSequence? = null
  override fun CharSequence?.write(parcel: Parcel, flags: Int) = Unit
}
