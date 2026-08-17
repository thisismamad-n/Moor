import { useStore } from '@nanostores/react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { useSessionView } from '@/app/chat/session-view'
import { Codicon } from '@/components/ui/codicon'
import { DropdownMenuItem, dropdownMenuRow } from '@/components/ui/dropdown-menu'
import type { HermesGateway } from '@/hermes'
import { useI18n } from '@/i18n'
import { modelOptionsQueryKey, requestModelOptions } from '@/lib/model-options'
import { currentPickerSelection } from '@/lib/model-status-label'
import { DEFAULT_REASONING_EFFORT } from '@/lib/reasoning-effort'
import { cn } from '@/lib/utils'
import { $modelPresets, applyModelPreset, modelPresetKey, setModelPreset } from '@/store/model-presets'
import { $visibleModels } from '@/store/model-visibility'
import { notifyError } from '@/store/notifications'
import {
  $defaultReasoningEffort,
  markComposerSelectionManual,
  setCurrentFastMode,
  setCurrentReasoningEffort
} from '@/store/session'
import { sessionTileDelegate } from '@/store/session-states'
import type { ModelOptionsResponse } from '@/types/hermes'

import { ModelCatalogMenu, type ModelMenuController } from './model-catalog-menu'

export { ModelMenuCloseContext } from './model-catalog-menu'

export interface ModelSelection {
  model: string
  provider: string
  /** Runtime id of the surface that opened the menu. When set, the switch
   *  targets that session (a tile) instead of the primary `$activeSessionId`. */
  sessionId?: null | string
}

interface ModelMenuPanelProps {
  gateway?: HermesGateway
  onSelectModel: (selection: ModelSelection) => Promise<boolean> | void
  profile?: string
  requestGateway: <T>(method: string, params?: Record<string, unknown>) => Promise<T>
}

/**
 * The composer's model menu: `ModelCatalogMenu` (the shared renderer) plus the
 * controller that gives a selection its meaning HERE — write through to this
 * surface's session, remember the pick as a global preset, keep the optimistic
 * stores honest, and roll back on a failed gateway write.
 */
export function ModelMenuPanel({ gateway, onSelectModel, profile = 'default', requestGateway }: ModelMenuPanelProps) {
  const { t } = useI18n()
  const copy = t.shell.modelMenu
  const [refreshing, setRefreshing] = useState(false)
  const queryClient = useQueryClient()
  // Bind to THIS surface's SessionView (primary or tile) so each pane's menu
  // shows/switches its own model — not the primary-only globals.
  const view = useSessionView()
  const activeSessionId = useStore(view.$runtimeId)
  const currentFastMode = useStore(view.$fast)
  const currentModel = useStore(view.$model)
  const currentProvider = useStore(view.$provider)
  const currentReasoningEffort = useStore(view.$reasoningEffort)
  const modelPresets = useStore($modelPresets)
  const defaultEffort = useStore($defaultReasoningEffort) || DEFAULT_REASONING_EFFORT
  const visibleModels = useStore($visibleModels)
  const touchesPrimary = view.kind === 'primary'

  // Subscribe to the SAME query the menu runs (identical key ⇒ React Query
  // dedupes, no second fetch). It must be a live subscription, not a cache
  // peek: with no model in the session store yet, currentPickerSelection falls
  // back to the catalog's reported current, and a non-reactive read would
  // never repaint that fallback once the catalog resolved.
  const modelOptions = useQuery({
    queryKey: modelOptionsQueryKey(profile, activeSessionId),
    queryFn: (): Promise<ModelOptionsResponse> => requestModelOptions({ gateway, sessionId: activeSessionId })
  })

  const { model: optionsModel, provider: optionsProvider } = currentPickerSelection(
    { model: currentModel, provider: currentProvider },
    modelOptions.data
  )

  // Explicit "Refresh Models": re-fetch the catalog with refresh:true so the
  // backend busts its 1h provider-model disk cache and re-pulls each provider's
  // live list. Fixes live-only models (e.g. OpenCode Zen free tier) vanishing
  // when the cache expires and falls back to the curated static list.
  const refreshModels = async () => {
    if (refreshing) {
      return
    }

    setRefreshing(true)

    try {
      const queryKey = modelOptionsQueryKey(profile, activeSessionId)

      const next = await requestModelOptions({ gateway, refresh: true, sessionId: activeSessionId })

      queryClient.setQueryData<ModelOptionsResponse>(queryKey, next)
    } catch {
      // Network/backend hiccup — fall back to a plain invalidate so the next
      // open re-fetches (still cached, but no worse than before).
      void queryClient.invalidateQueries({ queryKey: ['model-options'] })
    } finally {
      setRefreshing(false)
    }
  }

<<<<<<< HEAD
  // Selecting a model row restores that model's remembered preset onto the
  // session (effort/fast), gated by capability. Unset → Moor defaults.
  const selectFamily = async (family: ModelFamily, provider: ModelOptionProvider) => {
    const caps = provider.capabilities?.[family.id]
    const preset = modelPresets[modelPresetKey(provider.slug, family.id)] ?? {}
=======
  // Push a reasoning change onto the session that owns it, with rollback.
  const patchReasoning = async (next: string, previous: string, provider: string, model: string) => {
    if (touchesPrimary) {
      markComposerSelectionManual()
      setCurrentReasoningEffort(next)
    } else if (activeSessionId) {
      sessionTileDelegate()?.updateSession(activeSessionId, state => ({ ...state, reasoningEffort: next }))
    }
>>>>>>> upstream/main

    // Preset-only without a session: the gateway's `config.set` falls back to
    // global config when none matches — so don't reach it (preset + optimistic
    // store are the whole effect).
    if (!activeSessionId) {
      return
    }

    try {
      await requestGateway('config.set', { key: 'reasoning', session_id: activeSessionId, value: next })
    } catch (err) {
      if (touchesPrimary) {
        setCurrentReasoningEffort(previous)
      } else {
        sessionTileDelegate()?.updateSession(activeSessionId, state => ({ ...state, reasoningEffort: previous }))
      }

      setModelPreset(provider, model, { effort: previous })
      notifyError(err, t.shell.modelOptions.updateFailed)
    }
  }

  const patchFast = async (enabled: boolean, provider: string, model: string) => {
    if (touchesPrimary) {
      markComposerSelectionManual()
      setCurrentFastMode(enabled)
    } else if (activeSessionId) {
      sessionTileDelegate()?.updateSession(activeSessionId, state => ({ ...state, fast: enabled }))
    }

    if (!activeSessionId) {
      return
    }

    try {
      await requestGateway('config.set', {
        key: 'fast',
        session_id: activeSessionId,
        value: enabled ? 'fast' : 'normal'
      })
    } catch (err) {
      if (touchesPrimary) {
        setCurrentFastMode(!enabled)
      } else {
        sessionTileDelegate()?.updateSession(activeSessionId, state => ({ ...state, fast: !enabled }))
      }

      setModelPreset(provider, model, { fast: !enabled })
      notifyError(err, t.shell.modelOptions.fastFailed)
    }
  }

  const controller: ModelMenuController = {
    // Selecting a model row restores that model's remembered preset onto the
    // session (effort/fast). applyModelPreset owns the batched gateway write.
    applyPreset: (preset, row) => {
      setModelPreset(row.provider, row.model, preset)

      void applyModelPreset(preset, {
        failMessage: t.shell.modelOptions.updateFailed,
        primary: touchesPrimary,
        request: requestGateway,
        sessionId: activeSessionId
      })
    },

    current: {
      effort: currentReasoningEffort,
      fast: currentFastMode,
      model: optionsModel,
      provider: optionsProvider
    },

    presetFor: (provider, model) => modelPresets[modelPresetKey(provider, model)] ?? {},

    // The composer picker never persists the profile default. With a session it
    // scopes the switch to that session; with none it's UI state shipped on the
    // next session.create. Always stamp sessionId from this surface so a tile
    // switch never hits the primary (busy) session by accident.
    select: (model, provider) => onSelectModel({ model, provider, sessionId: activeSessionId || null }),

    setOptions: (patch, row) => {
      // Editing always records the model's global preset (keyed by
      // provider::model, not per-surface — a tile edit re-applies to that model
      // everywhere); the active model also gets it pushed onto its OWN session.
      // Non-active edits stay preset-only — no model switch, no session write.
      if (patch.effort !== undefined || patch.fast !== undefined) {
        setModelPreset(row.provider, row.model, patch)
      }

      if (!row.isActive) {
        return
      }

      if (patch.effort !== undefined) {
        void patchReasoning(patch.effort, currentReasoningEffort, row.provider, row.model)
      }

      if (patch.fast !== undefined) {
        void patchFast(patch.fast, row.provider, row.model)
      }
    }
  }

  return (
    <ModelCatalogMenu
      controller={controller}
      footer={
        <DropdownMenuItem
          className={cn(dropdownMenuRow, 'text-(--ui-text-tertiary)')}
          disabled={refreshing}
          onSelect={event => {
            event.preventDefault()
            void refreshModels()
          }}
        >
          <Codicon className={cn(refreshing && 'animate-spin')} name="sync" size="0.75rem" />
          {copy.refreshModels}
        </DropdownMenuItem>
<<<<<<< HEAD
      ) : groups.length === 0 && moaPresets.length === 0 ? (
        <DropdownMenuItem className={dropdownMenuRow} disabled>
          {copy.noModels}
        </DropdownMenuItem>
      ) : (
        <div className="max-h-[max(150px,30dvh)] overflow-y-auto py-0.5">
          {groups.map(group => (
            <DropdownMenuGroup className="py-0.5" key={group.provider.slug}>
              <DropdownMenuLabel className={dropdownMenuSectionLabel}>{group.provider.name}</DropdownMenuLabel>
              {group.families.map(family => {
                // The active id may be the base or its -fast sibling; either
                // way this one family row represents both.
                const activeId =
                  group.provider.slug === optionsProvider &&
                  (optionsModel === family.id || optionsModel === family.fastId)
                    ? optionsModel
                    : null

                const isCurrent = activeId !== null
                const name = modelDisplayParts(family.id).name
                // Capabilities are looked up against the active/base id; the
                // -fast variant carries the same param support as its base.
                const caps = group.provider.capabilities?.[family.id]

                // Effective settings for this row: live session state when it's
                // the active model, otherwise its remembered preset (Moor
                // defaults when unset). Row label AND submenu read from these so
                // they never disagree.
                const preset = modelPresets[modelPresetKey(group.provider.slug, family.id)] ?? {}
                const effEffort = isCurrent ? currentReasoningEffort : (preset.effort ?? '')
                const effFast = isCurrent ? currentFastMode : (preset.fast ?? false)

                const fastControl = resolveFastControl(
                  activeId ?? family.id,
                  group.provider.models ?? [],
                  caps?.fast ?? false,
                  effFast
                )

                const meta = [
                  fastControl.kind !== 'none' && fastControl.on ? copy.fast : null,
                  (caps?.reasoning ?? true) ? reasoningEffortLabel(effEffort) || copy.medium : null
                ]
                  .filter(Boolean)
                  .join(' ')

                // Every row is a hover-Edit submenu trigger. Activating it
                // (pointer or keyboard) switches to the family's base model and
                // restores its preset; the Fast toggle inside swaps to the -fast
                // sibling (or flips the speed param). The sub-trigger has no
                // `onSelect`, so wire both click and Enter/Space for keyboard parity.
                // Clicking the row commits the model and closes the picker; the
                // edit submenu (reasoning/fast) is reached by HOVER, so you can
                // still tweak those without the click dismissing everything.
                const activate = () => {
                  if (!isCurrent) {
                    void selectFamily(family, group.provider)
                  }

                  closeMenu()
                }

                return (
                  <DropdownMenuSub key={`${group.provider.slug}:${family.id}`}>
                    <DropdownMenuSubTrigger
                      className={dropdownMenuRow}
                      hideChevron
                      onClick={activate}
                      onKeyDown={event => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          activate()
                        }
                      }}
                    >
                      <span className="min-w-0 flex-1 truncate">
                        {name}
                        {meta ? <span className="text-(--ui-text-tertiary)"> {meta}</span> : null}
                      </span>
                      {isCurrent ? <Codicon className="ml-auto text-foreground" name="check" size="0.75rem" /> : null}
                    </DropdownMenuSubTrigger>
                    <ModelEditSubmenu
                      effort={effEffort}
                      fastControl={fastControl}
                      isActive={isCurrent}
                      model={family.id}
                      onSelectModel={nextModel => switchTo(nextModel, group.provider.slug)}
                      provider={group.provider.slug}
                      reasoning={caps?.reasoning ?? true}
                      requestGateway={requestGateway}
                    />
                  </DropdownMenuSub>
                )
              })}
            </DropdownMenuGroup>
          ))}
        </div>
      )}

      <DropdownMenuSeparator className="mx-0" />

      {moaPresets.length > 0 ? (
        <>
          <DropdownMenuLabel className={dropdownMenuSectionLabel}>MoA presets</DropdownMenuLabel>
          {moaPresets.map(preset => {
            const isCurrentMoa = optionsProvider === 'moa' && optionsModel === preset

            return (
              <DropdownMenuItem
                className={dropdownMenuRow}
                key={`moa:${preset}`}
                onSelect={event => {
                  event.preventDefault()
                  void selectMoaPreset(preset)
                }}
              >
                <span className="min-w-0 flex-1 truncate">MoA: {preset}</span>
                {isCurrentMoa ? <Codicon className="ml-auto text-foreground" name="check" size="0.75rem" /> : null}
              </DropdownMenuItem>
            )
          })}
          <DropdownMenuSeparator className="mx-0" />
        </>
      ) : null}

      <DropdownMenuItem
        className={cn(dropdownMenuRow, 'text-(--ui-text-tertiary)')}
        disabled={refreshing}
        onSelect={event => {
          event.preventDefault()
          void refreshModels()
        }}
      >
        <Codicon className={cn(refreshing && 'animate-spin')} name="sync" size="0.75rem" />
        {copy.refreshModels}
      </DropdownMenuItem>

      <DropdownMenuItem
        className={cn(dropdownMenuRow, 'text-(--ui-text-tertiary)')}
        onSelect={() => setModelVisibilityOpen(true)}
      >
        <Codicon name="settings-gear" size="0.75rem" />
        {copy.editModels}
      </DropdownMenuItem>
    </>
=======
      }
      gateway={gateway}
      includeMoa
      profile={profile}
      sessionId={activeSessionId}
    />
>>>>>>> upstream/main
  )
}
