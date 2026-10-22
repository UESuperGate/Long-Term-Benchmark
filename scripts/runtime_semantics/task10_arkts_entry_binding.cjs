'use strict';
function classifyEntry(nodes) {
  const visible = nodes.filter(node => node.visible === 'true');
  const one = id => visible.filter(node => node.id === id).length === 1;
  const canonicalQuality = ['media_caption', 'media_send', 'video_quality_selector'].every(one);
  const common = ['attachment_caption', 'attachment_send'].every(one);
  if (canonicalQuality && !common) return { binding: 'canonical_quality_ui', commonPreview: false, qualityPreview: true };
  if (!common || canonicalQuality) return { binding: 'unbound', commonPreview: false, qualityPreview: false };
  const additional = visible.filter(node => !['attachment_caption', 'attachment_send'].includes(node.id) &&
    (node.clickable === 'true' || ['Button', 'Toggle', 'Checkbox', 'Radio', 'Select', 'Slider', 'TextInput'].includes(node.type)));
  const originalSend = visible.find(node => node.id === 'attachment_send').text === 'Send original';
  if (!additional.length && originalSend) return { binding: 'canonical_original_media_ui', commonPreview: true, qualityPreview: false };
  return { binding: 'production_repository_probe_required', commonPreview: false, qualityPreview: false,
    additionalControls: additional.map(({ id, type, text, enabled }) => ({ id, type, text, enabled })) };
}
module.exports = { classifyEntry };
