/**
 * Which persisted keys are machine-level UI preferences (#145213).
 *
 * Only these leave localStorage for the machine's shared store, so native
 * Desktop and every browser that opens this machine's Webapp show the same
 * choices. Scoped families keep their scope inside the key name (a
 * `….profile.<name>` or per-connection suffix): only the location changes.
 *
 * Deliberately NOT here (they stay in this browser/window):
 * - credentials, grants and connection config: gateway registry, custom model
 *   endpoints, plugin decisions and preview-script grants, embed permissions;
 * - per-window or per-device runtime state: layout tree, open tiles and tabs,
 *   last route/session, scroll, zoom, pet and popout geometry, keep-awake;
 * - drafts, queues, journals and caches: composer queue, in-flight turns,
 *   pending/prepared submissions, previews, pricing, backend skin cache, the
 *   "provider configured" onboarding cache (each backend answers that itself);
 * - one-off notices: butterbar, update and real-profile prompts.
 */

const SHARED_KEYS: ReadonlySet<string> = new Set([
  // Appearance.
  'moor-desktop-theme-v2',
  'moor-desktop-mode-v1',
  'moor-desktop-profile-themes-v1',
  'moor-desktop-profile-modes-v1',
  'moor-desktop-user-themes-v1',
  'moor.desktop.backdrop.v1',
  'moor.desktop.chat-text-scale.v1',
  'moor.desktop.interfaceMode.v1',
  'moor.desktop.textDirection',
  'moor.desktop.translucency.v2',
  'moor.desktop.user-bubble-transparency.v1',
  // Sessions sidebar and profile rail.
  'moor.desktop.agentsGroupedByWorkspace',
  'moor.desktop.profileColors',
  'moor.desktop.profileOrder',
  'moor.desktop.profileRailVisible',
  'moor.desktop.sessionListDensity',
  'moor.desktop.sessionOrder',
  'moor.desktop.sessionOrder.manual',
  'moor.desktop.showAllProfiles',
  'moor.desktop.sidebarAgentsGrouped.allProfiles',
  'moor.desktop.sidebarCardRows',
  'moor.desktop.sidebarGrouping',
  'moor.desktop.sidebarGrouping.allProfiles',
  'moor.desktop.sidebarRowMeta',
  'moor.desktop.sidebarShowAllSessions',
  'moor.desktop.sidebarShowArchived',
  'moor.desktop.sidebarSortKey',
  // Status bar.
  'moor.desktop.statusbarHidden.v2',
  'moor.desktop.statusbarVisible.v2',
  // Transcript and tools.
  'moor.desktop.hideThreadTimeline',
  'moor.desktop.reasoning.collapsedByDefault',
  'moor.desktop.toolView.hideCodeDiffs',
  'moor.desktop.toolView.technical',
  // Shell, panes and behaviour.
  'moor.desktop.alwaysExternalLinks.v1',
  'moor.desktop.capabilities.catalogCardView',
  'moor.desktop.composerPopout.enabled',
  'moor.desktop.composerPopout.gesturesEnabled',
  'moor.desktop.files.showIgnored',
  'moor.desktop.keybinds',
  'moor.desktop.layoutPresets.v2',
  'moor.desktop.panesFlipped',
  'moor.desktop.tabStripDefault',
  'moor.desktop.titlebarAppActions',
  // Guidance: what the user already skipped, saw or dismissed does not come
  // back in every new browser or origin (#145600).
  'moor-onboarding-skipped-v1',
  'moor.desktop.tips.last.v1',
  'moor.desktop.tips.next.v1',
  'moor.desktop.tips.retired.v1',
  'moor.desktop.tips.rotation.v1',
  'moor.desktop.tips.shownAt.v1',
  'moor.desktop.tours.v1',
  // Sound and media.
  'moor.desktop.autoSpeakReplies',
  'moor.desktop.completionSoundVariantId',
  'moor.desktop.hapticsMuted',
  'moor.desktop.videoPlaybackSpeed',
  // Model picker.
  'moor.desktop.collapsed-providers',
  'moor.desktop.favorite-models',
  // visible-models is a diff against known-models: they only make sense together.
  'moor.desktop.known-models',
  'moor.desktop.model-presets',
  'moor.desktop.visible-models'
])

/** Families whose scope rides in the key suffix (gateway aliases/order/collapsed). */
const SHARED_PREFIXES: readonly string[] = ['moor.desktop.sidebar.gatewayGroups.v1.']

export function isSharedPreferenceKey(key: string): boolean {
  return SHARED_KEYS.has(key) || SHARED_PREFIXES.some(prefix => key.startsWith(prefix))
}
