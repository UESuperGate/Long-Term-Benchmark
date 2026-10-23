package org.wordpress.android.databinding

import android.content.Context
import android.content.res.ColorStateList
import android.view.LayoutInflater
import android.view.ViewGroup
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView

class AvatarView(context: Context) : ImageView(context) { var strokeColor: ColorStateList? = null }

class ItemChooseSiteBinding private constructor(val root: LinearLayout) {
    val avatar = AvatarView(root.context)
    val header = TextView(root.context).apply { layoutParams = ViewGroup.MarginLayoutParams(-1, -2) }
    val textTitle = TextView(root.context)
    val textDomain = TextView(root.context)
    val pin = ImageButton(root.context)
    val layoutContainer = LinearLayout(root.context)
    init { layoutContainer.addView(avatar); layoutContainer.addView(textTitle); layoutContainer.addView(textDomain); layoutContainer.addView(pin); root.addView(header); root.addView(layoutContainer) }
    companion object {
        fun inflate(inflater: LayoutInflater, parent: ViewGroup, attach: Boolean): ItemChooseSiteBinding =
            ItemChooseSiteBinding(LinearLayout(parent.context)).also { if (attach) parent.addView(it.root) }
        fun create(context: Context): ItemChooseSiteBinding = ItemChooseSiteBinding(LinearLayout(context))
    }
}
