package org.wordpress.android.fluxc.persistence

import org.wordpress.android.fluxc.model.PostModel
import org.wordpress.android.fluxc.store.PostStore

open class PostSqlUtils(private val store: PostStore) {
    open fun insertOrUpdatePost(post: PostModel, updateSlug: Boolean) {
        store.posts[post.remotePostId] = post
    }
}
