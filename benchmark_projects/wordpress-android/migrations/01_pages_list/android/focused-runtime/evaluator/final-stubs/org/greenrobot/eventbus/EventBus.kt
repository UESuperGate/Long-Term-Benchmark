package org.greenrobot.eventbus

annotation class Subscribe(val threadMode: ThreadMode = ThreadMode.POSTING)
enum class ThreadMode { POSTING, MAIN }
