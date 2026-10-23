package org.wordpress.android.fluxc.store

import org.wordpress.android.fluxc.model.PostModel
import org.wordpress.android.fluxc.model.SiteModel

data class AccountModel(var avatarUrl: String? = null, var userId: Long = 42)
open class AccountStore { open var account: AccountModel? = AccountModel() }

open class PostStore {
    val posts: MutableMap<Long, PostModel> = mutableMapOf()
    data class OnPostUploaded(val post: PostModel?, val isError: Boolean)
    open fun getPostByRemotePostId(id: Long, site: SiteModel): PostModel? = posts[id]
    open fun instantiatePostModel(site: SiteModel, isPage: Boolean, title: String, content: String,
        status: String, categories: String, format: String, publish: Boolean): PostModel = PostModel()
}
