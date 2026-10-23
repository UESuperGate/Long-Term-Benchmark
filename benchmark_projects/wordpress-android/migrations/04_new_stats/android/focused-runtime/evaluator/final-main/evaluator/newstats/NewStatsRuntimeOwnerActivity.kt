package evaluator.newstats

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.lifecycle.SavedStateHandle
import kotlinx.coroutines.Dispatchers
import org.wordpress.android.fluxc.model.SiteModel
import org.wordpress.android.fluxc.store.AccountStore
import org.wordpress.android.fluxc.utils.AppLogWrapper
import org.wordpress.android.ui.mysite.SelectedSiteRepository
import org.wordpress.android.ui.newstats.analytics.NewStatsTracker
import org.wordpress.android.ui.newstats.datasource.CountryViewsDataResult
import org.wordpress.android.ui.newstats.datasource.RegionViewsDataResult
import org.wordpress.android.ui.newstats.datasource.StatsDataSource
import org.wordpress.android.ui.newstats.datasource.StatsErrorType
import org.wordpress.android.ui.newstats.datasource.StatsVisitsDataResult
import org.wordpress.android.ui.newstats.locations.LocationsViewModel
import org.wordpress.android.ui.newstats.repository.StatsCardsConfigurationRepository
import org.wordpress.android.ui.newstats.repository.StatsRepository
import org.wordpress.android.ui.newstats.repository.StatsResultCache
import org.wordpress.android.ui.newstats.viewsstats.ViewsStatsViewModel
import org.wordpress.android.viewmodel.ResourceProvider
import java.lang.reflect.Proxy
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset
import java.util.ArrayDeque
import java.util.concurrent.CountDownLatch

data class VisitReply(
    val result: StatsVisitsDataResult,
    val gate: CountDownLatch? = null,
    val endDate: String? = null
)

class NewStatsRuntimeOwnerActivity : ComponentActivity() {
    val selectedSiteRepository = SelectedSiteRepository(SiteModel(siteId = 123))
    val accountStore = AccountStore("token")
    val resourceProvider = ResourceProvider()
    val tracker = NewStatsTracker()
    lateinit var cache: StatsResultCache
    lateinit var configuration: StatsCardsConfigurationRepository
    lateinit var repository: StatsRepository
    val visitsCalls = mutableListOf<Map<String, Any?>>()
    val countryCalls = mutableListOf<Map<String, Any?>>()
    val regionCalls = mutableListOf<Map<String, Any?>>()
    val visitsQueue = ArrayDeque<VisitReply>()
    val countryQueue = ArrayDeque<CountryViewsDataResult>()
    val regionQueue = ArrayDeque<RegionViewsDataResult>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        reset("2024-01-16T12:00:00Z")
    }

    fun reset(instant: String) {
        visitsCalls.clear(); countryCalls.clear(); regionCalls.clear()
        visitsQueue.clear(); countryQueue.clear(); regionQueue.clear()
        cache = StatsResultCache()
        configuration = StatsCardsConfigurationRepository(this)
        configuration.clear()
        val dataSource = Proxy.newProxyInstance(
            StatsDataSource::class.java.classLoader,
            arrayOf(StatsDataSource::class.java)
        ) { proxy, method, arguments ->
            if (method.declaringClass == Any::class.java) {
                return@newProxyInstance when (method.name) {
                    "toString" -> "ControlledStatsDataSource"
                    "hashCode" -> System.identityHashCode(proxy)
                    "equals" -> proxy === arguments?.firstOrNull()
                    else -> null
                }
            }
            val args = arguments.orEmpty()
            when (method.name) {
                "fetchStatsVisits" -> {
                    val reply = synchronized(visitsQueue) {
                        visitsCalls += mapOf(
                            "siteId" to args[0], "unit" to args[1].toString(), "quantity" to args[2],
                            "endDate" to args[3], "startDate" to args[4]
                        )
                        val endDate = args[3] as String
                        visitsQueue.firstOrNull { it.endDate == endDate }?.also { visitsQueue.remove(it) }
                            ?: visitsQueue.firstOrNull { it.endDate == null }?.also { visitsQueue.remove(it) }
                    }
                    if (reply == null) StatsVisitsDataResult.Error(StatsErrorType.NETWORK_ERROR)
                    else { reply.gate?.await(); reply.result }
                }
                "fetchCountryViews" -> synchronized(countryQueue) {
                    countryCalls += mapOf("siteId" to args[0], "range" to args[1].toString())
                    countryQueue.pollFirst() ?: CountryViewsDataResult.Error(StatsErrorType.NETWORK_ERROR)
                }
                "fetchRegionViews" -> synchronized(regionQueue) {
                    regionCalls += mapOf("siteId" to args[0], "range" to args[1].toString())
                    regionQueue.pollFirst() ?: RegionViewsDataResult.Error(StatsErrorType.NETWORK_ERROR)
                }
                else -> throw UnsupportedOperationException("unused datasource method ${method.name}")
            }
        } as StatsDataSource
        repository = StatsRepository(
            dataSource,
            cache,
            AppLogWrapper(),
            Clock.fixed(Instant.parse(instant), ZoneOffset.UTC),
            Dispatchers.IO
        )
    }

    fun newViews(saved: Map<String, Any?> = emptyMap()) = ViewsStatsViewModel(
        selectedSiteRepository,
        accountStore,
        repository,
        resourceProvider,
        SavedStateHandle(saved),
        configuration,
        tracker
    )

    fun newLocations() = LocationsViewModel(
        selectedSiteRepository,
        accountStore,
        repository,
        resourceProvider,
        tracker
    )

    fun enqueueVisit(result: StatsVisitsDataResult, gate: CountDownLatch? = null, endDate: String? = null) {
        synchronized(visitsQueue) { visitsQueue.addLast(VisitReply(result, gate, endDate)) }
    }
}
