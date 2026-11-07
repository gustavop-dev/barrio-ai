// Personas › Oportunidades: the opportunities grouped by stage, most advanced first, with «Cerradas sin
// acuerdo» folded. A card moves to another stage with a native drag (hold it, it lifts and follows the
// finger; every stage shows as a drop zone, and the list scrolls near its edges) or, as the accessible
// alternative, with its «Etapa» selector. Either way the move is optimistic and the toast offers «Deshacer».
import { useQueryClient } from '@tanstack/react-query';
import { useUpdateOportunidad } from '@compartido/api/hooks';
import { OPPORTUNITY_BOARD_KEY, useOpportunityBoard } from '@compartido/api/personas';
import { OPPORTUNITY_STAGES, type Opportunity, type OpportunityStage } from '@compartido/api/types';
import { closedMeta, movedToast, nextActionText, opportunityName, stageDays, stageGroups } from '@compartido/logic/barrio';
import { MODALITY_SHORT, OPPORTUNITY_STAGE_LABEL } from '@compartido/logic/personas';
import { router } from 'expo-router';
import { useCallback, useLayoutEffect, useRef, useState, type ComponentRef, type ReactNode } from 'react';
import { Pressable, RefreshControl, StyleSheet, View, type LayoutChangeEvent } from 'react-native';
import { GestureDetector, usePanGesture } from 'react-native-gesture-handler';
import Animated, {
  runOnJS,
  scrollTo,
  useAnimatedRef,
  useAnimatedStyle,
  useFrameCallback,
  useScrollViewOffset,
  useSharedValue,
  withSpring,
  type SharedValue,
} from 'react-native-reanimated';
import { Icon } from '@/components/icons';
import { useContentInsets } from '@/components/shell/useContentInsets';
import { Avatar, Badge, Button, EmptyState, EmptyText, ErrorRetry, Fold, Skeleton, T, pageContent, useToast } from '@/components/ui';
import { Select } from '@/components/ui/Select';
import { gestures, haptic, layout, spring } from '@/theme/motion';
import { colors, radius, shell, space } from '@/theme/tokens';
import { autoScrollDelta, stageAt, type DropZone } from './drag';
import { OportunidadForm } from './OportunidadForm';

const STAGE_OPTIONS = OPPORTUNITY_STAGES.map((value) => ({ value, label: OPPORTUNITY_STAGE_LABEL[value] }));
/** Half the gap between groups: a finger in the gap counts for the closest group. */
const ZONE_SLACK = space[6] / 2;

function openPerson(contactId: string) {
  router.push({ pathname: '/personas/[id]', params: { id: contactId } });
}

function PersonName({ opportunity, interactive }: { opportunity: Opportunity; interactive: boolean }) {
  const name = opportunityName(opportunity);
  const contact = opportunity.contact;
  if (contact && interactive) {
    return (
      <Pressable accessibilityRole="link" onPress={() => openPerson(contact.id)} style={styles.nameLink}>
        <T color={colors.brandDeep}>{name}</T>
      </Pressable>
    );
  }
  return <T>{name}</T>;
}

interface CardProps {
  opportunity: Opportunity;
  onMove: (opportunity: Opportunity, stage: OpportunityStage) => void;
  onEdit: (opportunity: Opportunity) => void;
  /** The lifted copy under the finger: no controls. */
  ghost?: boolean;
}

function CardBody({ opportunity, onMove, onEdit, ghost = false }: CardProps) {
  const next = nextActionText(opportunity);
  const name = opportunityName(opportunity);
  const days = stageDays(opportunity);
  return (
    <>
      <View style={styles.cardHead}>
        <Avatar name={name} />
        <View style={styles.grow}>
          <PersonName opportunity={opportunity} interactive={!ghost} />
          {opportunity.company ? (
            <T variant="detalle" soft>
              {opportunity.company}
            </T>
          ) : null}
        </View>
        <Badge tone="muted">{MODALITY_SHORT[opportunity.modality] ?? opportunity.modality}</Badge>
      </View>
      {next ? (
        <View style={styles.next}>
          <T variant="etiqueta" soft>
            Siguiente acción
          </T>
          <T>{next}</T>
        </View>
      ) : null}
      {days ? (
        <T variant="detalle" soft>
          {days}
        </T>
      ) : null}
      {ghost ? null : (
        <>
          <Select
            label="Etapa"
            accessibilityLabel={`Etapa de ${name}`}
            value={opportunity.stage}
            options={STAGE_OPTIONS}
            onChange={(stage) => onMove(opportunity, stage)}
            testID={`opp-stage-${opportunity.id}`}
          />
          <Button variant="ghost" size="small" style={styles.start} accessibilityLabel={`Editar la oportunidad con ${name}`} onPress={() => onEdit(opportunity)}>
            Editar
          </Button>
        </>
      )}
    </>
  );
}

/** What the cards share with the screen while one is dragged. */
interface DragContext {
  fingerY: SharedValue<number>;
  grabY: SharedValue<number>;
  hovered: SharedValue<string>;
  zones: SharedValue<DropZone[]>;
  rootTop: SharedValue<number>;
  scroll: SharedValue<number>;
  dragging: SharedValue<boolean>;
  onStart: (id: string) => void;
  onHover: (stage: string) => void;
  onDrop: (id: string, stage: string, canceled: boolean) => void;
}

function DraggableCard({ opportunity, ctx, dimmed, children }: { opportunity: Opportunity; ctx: DragContext; dimmed: boolean; children: ReactNode }) {
  const { fingerY, grabY, hovered, zones, rootTop, scroll, dragging, onStart, onHover, onDrop } = ctx;
  const id = opportunity.id;

  const pan = usePanGesture({
    testID: `opp-drag-${id}`,
    activateAfterLongPress: gestures.drag.longPressMs,
    onActivate: (event) => {
      'worklet';
      dragging.set(true);
      fingerY.set(event.absoluteY);
      grabY.set(event.y);
      hovered.set(opportunity.stage);
      runOnJS(onStart)(id);
    },
    onUpdate: (event) => {
      'worklet';
      fingerY.set(event.absoluteY);
      const stage = stageAt(zones.value, event.absoluteY - rootTop.value + scroll.value, ZONE_SLACK);
      if (stage !== hovered.value) {
        hovered.set(stage);
        runOnJS(onHover)(stage);
      }
    },
    onDeactivate: (event) => {
      'worklet';
      dragging.set(false);
      runOnJS(onDrop)(id, hovered.value, event.canceled);
    },
  });

  return (
    <GestureDetector gesture={pan}>
      <View
        testID={`opp-${id}`}
        accessibilityLabel={`${opportunityName(opportunity)}, ${OPPORTUNITY_STAGE_LABEL[opportunity.stage]}`}
        accessibilityHint="Mantén pulsada la tarjeta para arrastrarla a otra etapa, o usa el selector Etapa"
        style={[styles.card, dimmed ? styles.dimmed : null]}
      >
        {children}
      </View>
    </GestureDetector>
  );
}

function ClosedList({ items, onEdit }: { items: Opportunity[]; onEdit: (opportunity: Opportunity) => void }) {
  if (!items.length) return null;
  return (
    <Fold summary={`Cerradas sin acuerdo · ${items.length}`}>
      {items.map((opportunity) => {
        const name = opportunityName(opportunity);
        const meta = closedMeta(opportunity);
        return (
          <View key={opportunity.id} style={styles.closedRow}>
            <Avatar name={name} />
            <View style={styles.grow}>
              <PersonName opportunity={opportunity} interactive />
              {meta ? (
                <T variant="detalle" soft>
                  {meta}
                </T>
              ) : null}
            </View>
            <Button variant="ghost" size="small" accessibilityLabel={`Editar la oportunidad con ${name}`} onPress={() => onEdit(opportunity)}>
              Editar
            </Button>
          </View>
        );
      })}
    </Fold>
  );
}

export function Oportunidades({ header }: { header: ReactNode }) {
  const board = useOpportunityBoard();
  const update = useUpdateOportunidad();
  const client = useQueryClient();
  const toast = useToast();
  const { bottom } = useContentInsets();
  const [form, setForm] = useState<{ opportunity: Opportunity | null } | null>(null);
  const [drag, setDrag] = useState<{ id: string } | null>(null);
  const [hover, setHover] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const rootRef = useRef<ComponentRef<typeof View>>(null);
  const scrollRef = useAnimatedRef<Animated.ScrollView>();
  const scroll = useScrollViewOffset(scrollRef);
  const fingerY = useSharedValue(0);
  const grabY = useSharedValue(0);
  const hovered = useSharedValue('');
  const zones = useSharedValue<DropZone[]>([]);
  const rootTop = useSharedValue(0);
  const rootHeight = useSharedValue(0);
  const contentHeight = useSharedValue(0);
  const dragging = useSharedValue(false);
  const lift = useSharedValue(1);
  const layouts = useRef<Record<string, { y: number; height: number }>>({});
  const visible = useRef<string[]>([]);

  const items = board.data ?? [];

  const setStageLocally = (id: string, stage: OpportunityStage) => {
    client.setQueryData<Opportunity[]>(OPPORTUNITY_BOARD_KEY, (list) => list?.map((item) => (item.id === id ? { ...item, stage, days_in_stage: 0 } : item)));
  };

  const move = (opportunity: Opportunity, stage: OpportunityStage) => {
    if (stage === opportunity.stage) return;
    const previous = opportunity.stage;
    setStageLocally(opportunity.id, stage);
    update.mutate(
      { opportunityId: opportunity.id, patch: { stage } },
      {
        onSuccess: () => {
          haptic('actionSuccess');
          toast.show(movedToast(stage), {
            undo: () => {
              setStageLocally(opportunity.id, previous);
              update.mutate({ opportunityId: opportunity.id, patch: { stage: previous } });
            },
          });
        },
        onError: () => {
          setStageLocally(opportunity.id, previous);
          haptic('actionError');
          toast.show('No se pudo cambiar la etapa', { tone: 'error' });
        },
      },
    );
  };

  const measureRoot = useCallback(() => {
    rootRef.current?.measureInWindow((_x, y, _width, height) => {
      rootTop.set(y);
      rootHeight.set(height);
    });
  }, [rootTop, rootHeight]);

  const zoneLayout = (stage: string) => (event: LayoutChangeEvent) => {
    const { y, height } = event.nativeEvent.layout;
    layouts.current[stage] = { y, height };
    zones.set(
      visible.current.flatMap((key) => {
        const value = layouts.current[key];
        return value ? [{ stage: key, top: value.y, bottom: value.y + value.height }] : [];
      }),
    );
  };

  const onHover = (stage: string) => {
    setHover(stage);
    if (stage) haptic('dragOver');
  };

  // Near the top or bottom edge, the dragged card scrolls the list.
  const autoScroll = useFrameCallback((frame) => {
    'worklet';
    if (!dragging.value) return;
    const delta = autoScrollDelta(fingerY.value, rootTop.value, rootHeight.value, gestures.drag.autoScrollEdge, gestures.drag.autoScrollSpeed, frame.timeSincePreviousFrame ?? 16);
    if (!delta) return;
    const max = Math.max(0, contentHeight.value - rootHeight.value);
    const target = Math.min(max, Math.max(0, scroll.value + delta));
    if (target === scroll.value) return;
    scrollTo(scrollRef, 0, target, false);
    // The list moves under a still finger: the stage under it can change too.
    const stage = stageAt(zones.value, fingerY.value - rootTop.value + target, ZONE_SLACK);
    if (stage !== hovered.value) {
      hovered.set(stage);
      runOnJS(onHover)(stage);
    }
  }, false);

  const onStart = (id: string) => {
    measureRoot();
    haptic('dragStart');
    setDrag({ id });
    setHover(items.find((item) => item.id === id)?.stage ?? '');
    lift.set(withSpring(gestures.drag.liftScale, spring('dragLift')));
    autoScroll.setActive(true);
  };

  const onDrop = (id: string, stage: string, canceled: boolean) => {
    autoScroll.setActive(false);
    lift.set(withSpring(1, spring('dragLift')));
    setDrag(null);
    setHover('');
    const opportunity = items.find((item) => item.id === id);
    if (canceled || !opportunity || !stage || stage === opportunity.stage) return;
    if (!(OPPORTUNITY_STAGES as readonly string[]).includes(stage)) return;
    haptic('dragDrop');
    move(opportunity, stage as OpportunityStage);
  };

  const refresh = async () => {
    setRefreshing(true);
    try {
      await board.refetch();
    } finally {
      setRefreshing(false);
    }
  };

  const ctx: DragContext = { fingerY, grabY, hovered, zones, rootTop, scroll, dragging, onStart, onHover, onDrop };
  const edit = (opportunity: Opportunity) => setForm({ opportunity });
  const dragged = drag ? items.find((item) => item.id === drag.id) : undefined;
  const groups = stageGroups(items, Boolean(drag));
  const stagesShown = groups.map((group) => group.stage).join(' ');
  // The drop zones are the groups on screen (before their onLayout reports where they are).
  useLayoutEffect(() => {
    visible.current = stagesShown ? stagesShown.split(' ') : [];
  }, [stagesShown]);
  const closed = items.filter((item) => item.stage === 'sin_acuerdo');

  const ghost = useAnimatedStyle(() => ({
    transform: [{ translateY: fingerY.value - rootTop.value - grabY.value }, { scale: lift.value }],
  }));

  return (
    <View ref={rootRef} style={styles.root} onLayout={measureRoot}>
      <Animated.ScrollView
        ref={scrollRef}
        style={styles.root}
        contentContainerStyle={[pageContent, styles.content, { paddingBottom: bottom }]}
        scrollEnabled={!drag}
        onContentSizeChange={(_width, height) => contentHeight.set(height)}
        keyboardShouldPersistTaps="handled"
        testID="oportunidades-list"
        refreshControl={<RefreshControl refreshing={refreshing} enabled={!drag} onRefresh={() => void refresh()} tintColor={colors.brandDeep} colors={[colors.brandDeep]} />}
      >
        <View style={styles.header}>
          {header}
          <Button variant="primary" block icon={<Icon name="plus" size={20} color={colors.onBrand} />} onPress={() => setForm({ opportunity: null })}>
            Nueva oportunidad
          </Button>
          {board.isPending ? <Skeleton variant="card" count={2} label="Cargando oportunidades…" /> : null}
          <ErrorRetry error={board.error} onRetry={() => void board.refetch()} />
          {board.isSuccess && !items.length ? (
            <EmptyState title="Aún no hay oportunidades">
              <EmptyText>Regístrala cuando una conversación tenga una necesidad real. Así Resultados empieza a medir el negocio.</EmptyText>
            </EmptyState>
          ) : null}
        </View>

        {groups.map((group) => {
          const target = Boolean(drag) && hover === group.stage;
          return (
            <Animated.View
              key={group.stage}
              entering={layout.listEnter()}
              onLayout={zoneLayout(group.stage)}
              testID={`opp-zone-${group.stage}`}
              style={[styles.group, drag ? styles.zone : null, target ? styles.zoneOn : null]}
            >
              <T variant="etiqueta" soft accessibilityRole="header">
                {`${group.label} · ${group.items.length}`}
              </T>
              {group.items.map((opportunity) => (
                <Animated.View key={opportunity.id} entering={layout.listEnter()} layout={layout.listMove()}>
                  <DraggableCard opportunity={opportunity} ctx={ctx} dimmed={drag?.id === opportunity.id}>
                    <CardBody opportunity={opportunity} onMove={move} onEdit={edit} />
                  </DraggableCard>
                </Animated.View>
              ))}
              {drag && !group.items.length ? (
                <View style={styles.drop}>
                  <T variant="detalle" soft center>
                    Suéltala aquí
                  </T>
                </View>
              ) : null}
            </Animated.View>
          );
        })}

        <ClosedList items={closed} onEdit={edit} />
      </Animated.ScrollView>

      {drag && dragged ? (
        <Animated.View pointerEvents="none" style={[styles.ghost, ghost]} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          <View style={[styles.card, styles.lifted]}>
            <CardBody opportunity={dragged} onMove={move} onEdit={edit} ghost />
          </View>
        </Animated.View>
      ) : null}

      {form ? <OportunidadForm opportunity={form.opportunity} onClose={() => setForm(null)} /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.paper },
  content: { gap: space[6] },
  header: { gap: space[4] },
  group: { gap: space[3] },
  zone: { padding: space[2], margin: -space[2], borderRadius: radius.md, borderWidth: 1, borderStyle: 'dashed', borderColor: 'transparent' },
  zoneOn: { backgroundColor: colors.brandLight, borderColor: colors.brandDeep },
  drop: { minHeight: 56, justifyContent: 'center', borderWidth: 1, borderStyle: 'dashed', borderColor: colors.inkSoft, borderRadius: radius.md },
  card: { padding: space[4], gap: space[3], backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, borderRadius: radius.md },
  dimmed: { opacity: 0.35 },
  lifted: { borderColor: colors.brandDeep, elevation: 6, shadowColor: colors.ink, shadowOpacity: 0.18, shadowRadius: 12, shadowOffset: { width: 0, height: 6 } },
  ghost: { position: 'absolute', top: 0, left: shell.gutter, right: shell.gutter },
  cardHead: { flexDirection: 'row', alignItems: 'center', gap: space[3] },
  grow: { flex: 1, gap: 2 },
  nameLink: { minHeight: 44, justifyContent: 'center', alignSelf: 'flex-start' },
  next: { gap: 2 },
  start: { alignSelf: 'flex-start' },
  closedRow: { flexDirection: 'row', alignItems: 'center', gap: space[3], paddingVertical: space[2] },
});
