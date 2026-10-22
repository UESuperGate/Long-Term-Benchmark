package io.element.android.features.messages.impl.timeline
data class TimelineRoomInfo(val isDm: Boolean, val name: String, val userHasPermissionToSendMessage: Boolean, val userHasPermissionToSendReaction: Boolean, val isCallOngoing: Boolean)
