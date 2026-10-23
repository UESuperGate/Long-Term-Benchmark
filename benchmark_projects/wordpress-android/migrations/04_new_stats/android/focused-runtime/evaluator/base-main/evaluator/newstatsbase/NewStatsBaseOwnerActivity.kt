package evaluator.newstatsbase

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.lifecycle.SavedStateHandle
import org.wordpress.android.fluxc.store.AccountStore
import org.wordpress.android.ui.mysite.SelectedSiteRepository
import org.wordpress.android.ui.newstats.repository.StatsCardsConfigurationRepository
import org.wordpress.android.ui.newstats.repository.StatsRepository
import org.wordpress.android.ui.newstats.viewsstats.ChartType
import org.wordpress.android.ui.newstats.viewsstats.ViewsStatsViewModel
import org.wordpress.android.viewmodel.ResourceProvider

class NewStatsBaseOwnerActivity : ComponentActivity() {
    lateinit var viewModel: ViewsStatsViewModel

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        viewModel = ViewsStatsViewModel(
            SelectedSiteRepository(), AccountStore(), StatsRepository(), ResourceProvider(),
            SavedStateHandle(), StatsCardsConfigurationRepository(this)
        )
    }

    fun reachCommonEntry(): Map<String, Any?> {
        viewModel.onChartTypeChanged(ChartType.LINE)
        return mapOf(
            "activityClass" to javaClass.name,
            "commonAction" to "ViewsStatsViewModel.onChartTypeChanged",
            "selectedPeriod" to viewModel.selectedPeriod.value.toTypeString(),
            "targetActionsReachable" to false
        )
    }
}
