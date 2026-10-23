package org.wordpress.android.ui.main

import android.content.Intent
import android.os.Bundle
import android.view.MenuItem
import org.wordpress.android.WordPress

open class BaseAppCompatActivity {
    var application: Any = WordPress()
    val layoutInflater: Any = Any()
    var intent: Intent = Intent()
    var lastContentView: Any? = null
    val supportFragmentManager = FragmentManager()
    val onBackPressedDispatcher = BackDispatcher()
    protected open fun onCreate(savedInstanceState: Bundle?) {}
    protected open fun onNewIntent(intent: Intent) { this.intent = intent }
    open fun onOptionsItemSelected(item: MenuItem): Boolean = false
    fun setContentView(view: Any) { lastContentView = view }
    fun performCreate(bundle: Bundle? = null) { onCreate(bundle) }
    fun performNewIntent(value: Intent) { onNewIntent(value) }
}
class FragmentManager { fun findFragmentById(id: Int): Any? = null }
class BackDispatcher { var calls: Int = 0; fun onBackPressed() { calls += 1 } }
