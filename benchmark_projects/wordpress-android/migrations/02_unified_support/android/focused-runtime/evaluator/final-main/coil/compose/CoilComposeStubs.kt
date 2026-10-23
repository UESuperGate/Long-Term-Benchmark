package coil.compose

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale

@Composable
fun AsyncImage(model: Any?, contentDescription: String?, modifier: Modifier = Modifier) = Unit

@Composable
fun SubcomposeAsyncImage(
    model: Any?,
    contentDescription: String?,
    modifier: Modifier = Modifier,
    contentScale: ContentScale = ContentScale.Fit,
    loading: @Composable () -> Unit = {},
    error: @Composable () -> Unit = {},
) = Unit
