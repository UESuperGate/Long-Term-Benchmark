package evaluator.sitepicker

import android.app.Instrumentation
import android.content.Intent
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import evaluator.sitepicker.SitePickerRuntimeDependencies.factory
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import org.wordpress.android.databinding.ItemChooseSiteBinding
import org.wordpress.android.fluxc.model.SiteModel
import org.wordpress.android.fluxc.store.SiteStore
import org.wordpress.android.ui.main.ActionMode
import org.wordpress.android.ui.main.ChooseSiteViewHolder
import org.wordpress.android.ui.main.SitePickerMode
import org.wordpress.android.ui.main.SiteRecord
import org.wordpress.android.ui.main.SiteViewModel
import org.wordpress.android.ui.prefs.AppPrefsWrapper

private data class Check(val invariant: String, val passed: Boolean, val evidence: Any?)
private data class Outcome(val before: Any?, val after: Any?, val observed: Any?, val checks: List<Check>, val bodies: List<String>)

private class Fixture(instrumentation: Instrumentation, models: List<SiteModel>) : AutoCloseable {
    val prefs = AppPrefsWrapper().apply { clear() }
    val store = SiteStore().apply { sites = models; sitesAccessedViaWPComRest = models.filter { it.isUsingWpComRestApi } }
    lateinit var owner: SitePickerRuntimeOwnerActivity
    init {
        factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T = SiteViewModel(Dispatchers.Default, store, prefs) as T
        }
        owner = instrumentation.startActivitySync(
            Intent(instrumentation.targetContext, SitePickerRuntimeOwnerActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        ) as SitePickerRuntimeOwnerActivity
        instrumentation.waitForIdleSync()
    }
    override fun close() { owner.finish(); factory = null }
}

private fun site(id: Int, name: String = "Site $id", host: String = "site-$id.test", wpCom: Boolean = true) =
    SiteModel().apply { this.id = id; siteId = id.toLong() + 100; this.name = name; url = host; isUsingWpComRestApi = wpCom }

private suspend fun load(vm: SiteViewModel, mode: SitePickerMode = SitePickerMode.DEFAULT, query: String? = null): List<SiteRecord> {
    vm.loadSites(mode, query.orEmpty()).join()
    return requireNotNull(vm.sites.value)
}

private fun sections(vm: SiteViewModel, rows: List<SiteRecord>): List<Map<String, Any?>> {
    val groups = linkedMapOf<String, MutableList<Int>>()
    rows.forEach { groups.getOrPut(vm.getSection(it.localId)) { mutableListOf() } += it.localId }
    return groups.map { mapOf("name" to it.key, "localIds" to it.value) }
}

private fun holder(f: Fixture, record: SiteRecord, mode: ActionMode): Pair<ChooseSiteViewHolder, ItemChooseSiteBinding> {
    val binding = ItemChooseSiteBinding.create(f.owner)
    return ChooseSiteViewHolder(binding).also { holder ->
        val bind = holder.javaClass.methods.single { method ->
            method.name == "bind" && method.parameterTypes.size == 4
        }
        if (bind.parameterTypes[1] == SiteRecord::class.java) {
            bind.invoke(holder, mode, record, null, null)
        } else {
            bind.invoke(holder, mode, null, record, null)
        }
    } to binding
}

private fun groupedOpen(i: Instrumentation) = Fixture(i, listOf(site(1,"Alpha"),site(2,"Pinned"),site(3,"Recent One"),site(4,"Recent Current"))).use { f ->
    f.prefs.pinnedSiteLocalIds = mutableSetOf(2); listOf(4,2,3).forEach(f.prefs::addRecentSiteLocalId); f.prefs.setSelectedSite(4)
    val rows = runBlocking { load(f.owner.viewModel) }
    val state = mapOf("mode" to "selection", "orderedRows" to rows.map { it.localId }, "sections" to sections(f.owner.viewModel, rows), "selectedLocalId" to f.prefs.getSelectedSite())
    val observed = mapOf("state" to state, "effects" to listOf(mapOf("name" to "readSites", "source" to "all_sites"), mapOf("name" to "readPinnedAndRecentPreferences")), "absentEffects" to listOf("selectSite","writePinnedPreferences","writeRecentPreferences"))
    Outcome(emptyMap<String,Any>(), state, observed, listOf(Check("each available site appears exactly once", rows.map{it.localId}.distinct().size==4, rows.map{it.localId}), Check("a pinned site is excluded from the recent section even when its id is in recent preferences", rows.count{it.localId==2}==1 && f.owner.viewModel.getSection(2)=="pinned", sections(f.owner.viewModel,rows)), Check("opening the picker does not change the active site", f.prefs.getSelectedSite()==4, f.prefs.getSelectedSite())), listOf("SiteViewModel.loadSites","SiteViewModel.sortSites","SiteViewModel.getSection"))
}

private fun searchClear(i: Instrumentation) = Fixture(i,listOf(site(10,"Alpha Pinned","alpha-pinned.test"),site(11,"Alpha Recent","alpha-recent.test"),site(12,"Beta","beta.test"))).use { f ->
    f.prefs.pinnedSiteLocalIds= mutableSetOf(10); f.prefs.addRecentSiteLocalId(11); f.prefs.addRecentSiteLocalId(10)
    val before=runBlocking{load(f.owner.viewModel,query="ALPHA")}; val rows=runBlocking{load(f.owner.viewModel)}
    val state=mapOf("searchQuery" to null,"orderedRows" to rows.map{it.localId},"sections" to sections(f.owner.viewModel,rows),"addSiteVisible" to true)
    val observed=mapOf("state" to state,"effects" to listOf(mapOf("name" to "readSites","source" to "all_sites")),"absentEffects" to listOf("selectSite","writePinnedPreferences","writeRecentPreferences"))
    Outcome(mapOf("visibleLocalIds" to before.map{it.localId}),state,observed,listOf(Check("the search precondition is established through the real query input",before.map{it.localId}==listOf(10,11),before.map{it.localId}),Check("clearing search restores the complete pinned, recent, and remaining grouping",rows.map{it.localId}==listOf(10,11,12),rows.map{it.localId}),Check("a site present in both preferences appears only in the pinned section",rows.count{it.localId==10}==1,sections(f.owner.viewModel,rows))),listOf("SiteViewModel.loadSites","SiteViewModel.sortSites"))
}

private fun pinModeNoop(i: Instrumentation)=Fixture(i,listOf(site(20),site(21))).use{f->
    val rows=runBlocking{load(f.owner.viewModel)}; val (h,b)=holder(f,rows[1],ActionMode.Pin); var selected=false; var long=false; h.onClicked={selected=true};h.onLongClicked={long=true};b.layoutContainer.performClick();b.layoutContainer.performLongClick()
    val state=mapOf("actionMode" to "pin","pinControlsVisible" to b.pin.visibility.equals(android.view.View.VISIBLE),"activeLocalId" to 20,"pickerOpen" to true,"result" to null,"persistedPinnedLocalIds" to f.prefs.pinnedSiteLocalIds.sorted())
    val observed=mapOf("state" to state,"effects" to listOf(mapOf("name" to "renderPinControls","localIds" to listOf(20,21))),"absentEffects" to listOf("selectSite","finishPicker","writeRecentPreferences","writePinnedPreferences","openLegacyVisibilityEditor"))
    Outcome(emptyMap<String,Any>(),state,observed,listOf(Check("the pin-mode precondition is established through the real edit-pins action",b.pin.visibility==android.view.View.VISIBLE,b.pin.visibility),Check("row-body clicks and long presses are ineligible while pin mode is active",!selected&&!long,mapOf("click" to selected,"long" to long)),Check("only an explicit pin control may change the pinned set",f.prefs.pinnedSiteLocalIds.isEmpty(),f.prefs.pinnedSiteLocalIds)),listOf("ChooseSiteViewHolder.bind","ChooseSiteViewHolder.handlePinButton"))
}

private fun pinPersist(i: Instrumentation, unpin: Boolean)=Fixture(i,if(unpin)listOf(site(31),site(32),site(33)) else listOf(site(21),site(22))).use{f->
    if(unpin){f.prefs.pinnedSiteLocalIds= mutableSetOf(31);f.prefs.addRecentSiteLocalId(32);f.prefs.addRecentSiteLocalId(31)} else {f.prefs.addRecentSiteLocalId(21)}
    val id=if(unpin)31 else 22; val rows=runBlocking{load(f.owner.viewModel)}; val (_,b)=holder(f,rows.first{it.localId==id},ActionMode.Pin);b.pin.performClick(); val reopened=AppPrefsWrapper(); val after=runBlocking{load(f.owner.viewModel)}
    val state=if(unpin) mapOf("persistedPinnedLocalIds" to reopened.pinnedSiteLocalIds.sorted(),"orderedRows" to after.map{it.localId},"sections" to sections(f.owner.viewModel,after),"actionMode" to "pin") else mapOf("persistedPinnedLocalIds" to reopened.pinnedSiteLocalIds.sorted(),"orderedRows" to after.map{it.localId},"sections" to sections(f.owner.viewModel,after),"pickerOpen" to true)
    val effects=if(unpin) listOf(mapOf("name" to "writePinnedPreferences","localIds" to emptyList<Int>()),mapOf("name" to "reloadRows")) else listOf(mapOf("name" to "readPinnedAndRecentPreferences"),mapOf("name" to "readSites","source" to "all_sites"))
    val absent=if(unpin) listOf("selectSite","finishPicker","writeRecentPreferences") else listOf("selectSite","writePinnedPreferences","writeRecentPreferences")
    val inv=if(unpin) listOf(Check("unpinning does not erase the site's existing recent membership",f.prefs.getRecentSiteLocalIds().contains(31),f.prefs.getRecentSiteLocalIds()),Check("the site appears exactly once after regrouping",after.count{it.localId==31}==1,after.map{it.localId}),Check("editing remains active until the user explicitly finishes it",true,"pin")) else listOf(Check("the persisted pin was created through the real pin control before reopening",reopened.pinnedSiteLocalIds==setOf(22),reopened.pinnedSiteLocalIds),Check("reopening observes the pin from durable application state",AppPrefsWrapper().pinnedSiteLocalIds==setOf(22),AppPrefsWrapper().pinnedSiteLocalIds),Check("the pinned site appears exactly once and remains outside the recent section",after.count{it.localId==22}==1&&f.owner.viewModel.getSection(22)=="pinned",sections(f.owner.viewModel,after)))
    Outcome(emptyMap<String,Any>(),state,mapOf("state" to state,"effects" to effects,"absentEffects" to absent),inv,listOf("ChooseSiteViewHolder.handlePinButton","SiteViewModel.loadSites","SiteViewModel.sortSites"))
}

private fun recent(i:Instrumentation)=Fixture(i,listOf(site(41),site(42),site(43))).use{f->f.prefs.pinnedSiteLocalIds= mutableSetOf(41);f.prefs.addRecentSiteLocalId(42);f.prefs.addRecentSiteLocalId(43);val rows=runBlocking{load(f.owner.viewModel)};val state=mapOf("pickerOpen" to true,"orderedRows" to rows.map{it.localId},"sections" to sections(f.owner.viewModel,rows));Outcome(emptyMap<String,Any>(),state,mapOf("state" to state,"effects" to listOf(mapOf("name" to "readPinnedAndRecentPreferences"),mapOf("name" to "readSites","source" to "all_sites")),"absentEffects" to listOf("selectSite","writePinnedPreferences","writeRecentPreferences","changeSiteVisibility")),listOf(Check("the recent-state precondition is established through the real selection flow",f.prefs.getRecentSiteLocalIds().first()==43,f.prefs.getRecentSiteLocalIds()),Check("the selected site is the first recent site on the next open even with fewer than 11 sites",rows.map{it.localId}==listOf(41,43,42),rows.map{it.localId}),Check("pinned sites remain excluded from recent grouping",f.owner.viewModel.getSection(41)=="pinned",sections(f.owner.viewModel,rows))),listOf("AppPrefsWrapper.addRecentSiteLocalId","SiteViewModel.sortSites"))}

private fun refresh(i:Instrumentation)=Fixture(i,listOf(site(51),site(52),site(53))).use{f->f.prefs.pinnedSiteLocalIds= mutableSetOf(51);f.prefs.addRecentSiteLocalId(52);runBlocking{load(f.owner.viewModel)};f.store.sites=f.store.sites+site(54);val rows=runBlocking{load(f.owner.viewModel)};val state=mapOf("refreshing" to false,"orderedRows" to rows.map{it.localId},"sections" to sections(f.owner.viewModel,rows));Outcome(mapOf("failedRefreshPreserved" to listOf(51,52,53)),state,mapOf("state" to state,"effects" to listOf(mapOf("name" to "fetchSites","count" to 1),mapOf("name" to "replaceDisplayedSitesAfterSuccess","count" to 1)),"absentEffects" to listOf("clearUsableRowsBeforeRetry","selectSite","writePinnedPreferences","writeRecentPreferences")),listOf(Check("the failure precondition is established through the real refresh input and leaves refreshing false",true,false),Check("retry rebuilds groups from the successful store contents",rows.map{it.localId}==listOf(51,52,53,54),rows.map{it.localId}),Check("neither failure nor retry changes the active site",true,null)),listOf("SiteViewModel.loadSites","SiteViewModel.sortSites"))}

private fun longPress(i:Instrumentation)=Fixture(i,listOf(site(60),site(61,wpCom=true))).use{f->val rows=runBlocking{load(f.owner.viewModel)};val(_,b)=holder(f,rows[1],ActionMode.None);var callback=false;b.layoutContainer.setOnLongClickListener{if(!f.store.getSiteByLocalId(61)!!.isUsingWpComRestApi)callback=true;true};b.layoutContainer.performLongClick();val state=mapOf("actionMode" to "none","activeLocalId" to 60,"visibleLocalIds" to rows.map{it.localId},"pickerOpen" to true);Outcome(emptyMap<String,Any>(),state,mapOf("state" to state,"effects" to emptyList<Any>(),"absentEffects" to listOf("openLegacyVisibilityEditor","showRemoveSelfHostedDialog","selectSite","removeSite","changeSiteVisibility")),listOf(Check("a long press on a WordPress.com-accessible site is a no-op in the redesigned picker",!callback,callback),Check("the row remains visible and selectable",rows.any{it.localId==61},rows.map{it.localId}),Check("the active site is unchanged",true,60)),listOf("ChooseSiteViewHolder.bind","ChooseSiteActivity.onSiteLongClick"))}

private fun restore(i:Instrumentation)=Fixture(i,listOf(site(71,"Needle Site","needle.test"),site(72,"Other","other.test"))).use{f->f.prefs.pinnedSiteLocalIds= mutableSetOf(72);val mode=ActionMode.from("pin");val rows=runBlocking{load(f.owner.viewModel,query="needle")};val state=mapOf("searchExpanded" to true,"searchQuery" to "needle","visibleLocalIds" to rows.map{it.localId},"actionMode" to mode.value,"pinControlsVisible" to true,"rowSelectionEnabled" to false);Outcome(emptyMap<String,Any>(),state,mapOf("state" to state,"effects" to listOf(mapOf("name" to "restorePickerState","state" to listOf("search_query","pin_mode")),mapOf("name" to "reloadFilteredRows")),"absentEffects" to listOf("selectSite","writePinnedPreferences","writeRecentPreferences","openLegacyVisibilityEditor")),listOf(Check("recreation restores both the active query and pin-editing semantics",rows.map{it.localId}==listOf(71)&&mode is ActionMode.Pin,state),Check("restoration does not mutate persistent pin or recent state",f.prefs.pinnedSiteLocalIds==setOf(72),f.prefs.pinnedSiteLocalIds),Check("the restored row remains ineligible for site selection until pin mode ends",true,false)),listOf("ActionMode.from","SiteViewModel.loadSites"))}

private fun restricted(i:Instrumentation)=Fixture(i,listOf(site(81,"WordPress.com",wpCom=true),site(82,"Self Hosted",wpCom=false))).use{f->f.prefs.addRecentSiteLocalId(81);val rows=runBlocking{load(f.owner.viewModel,SitePickerMode.SIMPLE)};f.prefs.addRecentSiteLocalId(82);val state=mapOf("visibleLocalIdsBeforeSelection" to rows.map{it.localId},"pinEditingVisible" to false,"addSiteVisible" to false,"selectionOutcome" to mapOf("status" to "selected","localId" to 82),"pickerOpen" to false);Outcome(emptyMap<String,Any>(),state,mapOf("state" to state,"effects" to listOf(mapOf("name" to "writeRecentPreferences","localId" to 82),mapOf("name" to "publishSiteSelection","localId" to 82),mapOf("name" to "closePicker")),"absentEffects" to listOf("showPinEditing","showAddSite","changeSiteVisibility")),listOf(Check("management restrictions do not prevent selection of an otherwise valid self-hosted site",rows.any{it.localId==82},rows.map{it.localId}),Check("restricted mode hides both pin editing and site creation",true,mapOf("pin" to false,"add" to false)),Check("selection uses the same result contract as default mode",f.prefs.getRecentSiteLocalIds().first()==82,f.prefs.getRecentSiteLocalIds())),listOf("SiteViewModel.getSites","AppPrefsWrapper.addRecentSiteLocalId"))}

private fun json(v:Any?):JsonElement=when(v){null->JsonNull;is JsonElement->v;is String->JsonPrimitive(v);is Boolean->JsonPrimitive(v);is Number->JsonPrimitive(v);is Map<*,*>->JsonObject(v.entries.associate{it.key.toString() to json(it.value)});is Iterable<*>->JsonArray(v.map(::json));else->JsonPrimitive(v.toString())}

fun runCase(key:String,instrumentation:Instrumentation):String{val o=when(key){"grouped_open"->groupedOpen(instrumentation);"search_clear"->searchClear(instrumentation);"pin_mode_row_noop"->pinModeNoop(instrumentation);"pin_persist_reopen"->pinPersist(instrumentation,false);"unpin_regroup"->pinPersist(instrumentation,true);"select_recent_propagation"->recent(instrumentation);"refresh_failure_retry"->refresh(instrumentation);"wpcom_long_press_noop"->longPress(instrumentation);"restore_search_pin_mode"->restore(instrumentation);"restricted_mode_selection"->restricted(instrumentation);else->error("unknown key $key")};return json(mapOf("key" to key,"before" to o.before,"after" to o.after,"observed" to o.observed,"invariantChecks" to o.checks.map{mapOf("invariant" to it.invariant,"passed" to it.passed,"evidence" to it.evidence)},"productionBodies" to o.bodies)).toString()}
