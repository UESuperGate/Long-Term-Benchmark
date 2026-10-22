package runtime

import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import runtime.foundation.EvidenceRobolectricRunner

@RunWith(EvidenceRobolectricRunner::class)
@Config(sdk = [36])
class ProductionEntryProbe {
    private fun inspect(name: String, featureField: String) {
        val type = Class.forName(name)
        val fields = type.declaredFields.map { it.name }.sorted()
        val constructors = type.declaredConstructors.map { it.parameterCount }
        Evidence.record("loaded_common_production_state", "class" to type.name,
            "fields" to fields, "constructors" to constructors)
        check(constructors.isNotEmpty()) { "Common production state is not loadable" }
        Evidence.record("runtime_entry_capability", "featureField" to featureField,
            "fullFeatureEntry" to fields.contains(featureField))
        Evidence.observe("fullFeatureEntry" to fields.contains(featureField),
            "class" to type.name, "fields" to fields)
    }

    @Test fun task10_entry() = inspect(
        "io.element.android.features.messages.impl.attachments.preview.AttachmentsPreviewState",
        "mediaOptimizationSelectorState")

    @Test fun task11_entry() = inspect(
        "io.element.android.features.messages.impl.MessagesState", "successorRoom")
}
