package org.signal.registration.screens.util

import org.signal.registration.RegistrationFlowEvent
import org.signal.registration.RegistrationRoute

fun ((RegistrationFlowEvent) -> Unit).navigateTo(route: RegistrationRoute) = invoke(RegistrationFlowEvent.NavigateToScreen(route))
fun ((RegistrationFlowEvent) -> Unit).navigateBack() = invoke(RegistrationFlowEvent.NavigateBack)
