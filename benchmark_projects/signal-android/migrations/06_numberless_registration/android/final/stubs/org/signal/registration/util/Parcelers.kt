package org.signal.registration.util

import android.os.Parcel
import kotlinx.parcelize.Parceler

object AccountEntropyPoolParceler : Parceler<org.signal.core.models.AccountEntropyPool?> { override fun create(parcel: Parcel) = null; override fun org.signal.core.models.AccountEntropyPool?.write(parcel: Parcel, flags: Int) = Unit }
object MasterKeyParceler : Parceler<org.signal.core.models.MasterKey?> { override fun create(parcel: Parcel) = null; override fun org.signal.core.models.MasterKey?.write(parcel: Parcel, flags: Int) = Unit }
object NullableACIParceler : Parceler<org.signal.core.models.ServiceId.ACI?> { override fun create(parcel: Parcel) = null; override fun org.signal.core.models.ServiceId.ACI?.write(parcel: Parcel, flags: Int) = Unit }
object NullableSessionMetadataParceler : Parceler<org.signal.network.api.RegistrationApiV2.SessionMetadata?> { override fun create(parcel: Parcel) = null; override fun org.signal.network.api.RegistrationApiV2.SessionMetadata?.write(parcel: Parcel, flags: Int) = Unit }
