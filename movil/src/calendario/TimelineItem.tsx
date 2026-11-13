// A row of the timeline (the PWA's TimelineItem): layer dot, hour, the sentence, an optional line under
// it, the state badge when it is not a normal success, the role's portrait, folded content and links.
// The sentence and the line under it take 2 lines each (with «…») when the whole is one tap away: in the folded
// content («Ver más» unfolds them too) or in what «Abrir» / LinkedIn opens. Without either, they stay whole.
//
// Compact (the day panel): only the dot, the hour and the sentence in one line with «…», plus a chevron. A tap on the
// row unfolds it in place: the whole sentence, the line under it, the badge, the folded content and the links; another
// tap folds it again. What stays at the row's end (`aside`, the «Hecho» of a resolved item) shows folded too.
import type { Tone } from '@compartido/logic/tone';
import { useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Animated, { useAnimatedStyle, withTiming } from 'react-native-reanimated';
import { Icon } from '@/components/icons';
import { AgentPortrait, Badge, FoldIn, T } from '@/components/ui';
import { isHttps, openLink } from '@/navigation';
import { timing } from '@/theme/motion';
import { colors, radius, shell, space } from '@/theme/tokens';

// Built on the JS thread: timing() is not a worklet, and calling it inside a style worklet crashes the app on the UI
// runtime («Tried to synchronously call a Remote Function»).
const FOLD = timing('fold');

/** Lines of the sentence and of the line under it while their whole is one tap away. */
export const TIMELINE_LINES = 2;

const DOT = 10;
const TIME_WIDTH = 44;
/** The unfolded content of a compact row starts under the sentence, past the dot and the hour. */
const BODY_INDENT = DOT + TIME_WIDTH + 2 * space[3];

export interface TimelineItemProps {
  /** Dot colour: the layer's, or tinta-suave for the small items. */
  color: string;
  /** «09:00», or null for all-day items. */
  time?: string | null;
  title: string;
  sub?: string | null;
  badge?: { label: string; tone: Tone } | null;
  agent?: string | null;
  /** In-app destination: «Abrir» (or `linkLabel`). */
  to?: string | null;
  linkLabel?: string;
  /** LinkedIn URL: «Ver en LinkedIn ↗» (https only). */
  externalUrl?: string | null;
  /** Folded content (post excerpt, the full comment, «Por qué»). */
  children?: ReactNode;
  expandLabel?: string;
  /** One line with «…» that a tap on the row unfolds, with everything else (the day panel). */
  compact?: boolean;
  /** At the row's end, also while it is folded (compact rows only). */
  aside?: ReactNode;
  testID?: string;
}

function Links({ to, linkLabel, external }: { to?: string | null; linkLabel: string; external?: string | null }) {
  if (!to && !external) return null;
  return (
    <View style={styles.links}>
      {to ? (
        <Pressable accessibilityRole="link" onPress={() => openLink(to)} style={styles.link}>
          <T variant="detalle" color={colors.brandDeep}>
            {linkLabel}
          </T>
        </Pressable>
      ) : null}
      {external ? (
        <Pressable accessibilityRole="link" accessibilityHint="Se abre fuera de la app" onPress={() => openLink(external)} style={[styles.link, styles.externalLink]}>
          <T variant="detalle" color={colors.brandDeep}>
            Ver en LinkedIn
          </T>
          <Icon name="external" size={16} color={colors.brandDeep} />
        </Pressable>
      ) : null}
    </View>
  );
}

function StateBadge({ badge }: { badge: TimelineItemProps['badge'] }) {
  if (!badge) return null;
  return (
    <View style={styles.badge}>
      <Badge tone={badge.tone}>{badge.label}</Badge>
    </View>
  );
}

/** The day panel's row: one line until a tap unfolds it in place. */
function CompactItem({ color, time, title, sub, badge, agent, to, linkLabel = 'Abrir', externalUrl, children, aside, testID }: TimelineItemProps) {
  const [open, setOpen] = useState(false);
  const external = isHttps(externalUrl) ? externalUrl : null;
  const chevron = useAnimatedStyle(() => ({ transform: [{ rotate: withTiming(open ? '180deg' : '0deg', FOLD) }] }), [open]);
  return (
    <View style={styles.compact} testID={testID} collapsable={false}>
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityHint={open ? 'Pliega el detalle' : 'Muestra el detalle'}
        onPress={() => setOpen((value) => !value)}
        style={styles.compactHead}
      >
        <View style={[styles.dot, styles.compactDot, { backgroundColor: color }]} />
        <T variant="detalle" soft style={styles.time}>
          {time || ''}
        </T>
        {agent ? <AgentPortrait role={agent} size="sm" /> : null}
        <T style={styles.title} numberOfLines={open ? undefined : 1}>
          {title}
        </T>
        {aside}
        <Animated.View style={chevron}>
          <Icon name="chevronDown" size={20} color={colors.inkSoft} />
        </Animated.View>
      </Pressable>
      {open ? (
        <FoldIn style={styles.compactMore}>
          {sub ? (
            <T variant="detalle" soft>
              {sub}
            </T>
          ) : null}
          <StateBadge badge={badge} />
          {children ? <View style={styles.content}>{children}</View> : null}
          <Links to={to} linkLabel={linkLabel} external={external} />
        </FoldIn>
      ) : null}
    </View>
  );
}

export function TimelineItem(props: TimelineItemProps) {
  const { color, time, title, sub, badge, agent, to, linkLabel = 'Abrir', externalUrl, children, expandLabel = 'Ver más', compact = false, testID } = props;
  const [open, setOpen] = useState(false);
  if (compact) return <CompactItem {...props} />;
  const external = isHttps(externalUrl) ? externalUrl : null;
  const lines = !open && (children || to || external) ? TIMELINE_LINES : undefined;
  return (
    <View style={styles.item} testID={testID} collapsable={false}>
      <View style={[styles.dot, { backgroundColor: color }]} />
      <T variant="detalle" soft style={styles.time}>
        {time || ''}
      </T>
      <View style={styles.body}>
        <View style={styles.titleRow}>
          {agent ? <AgentPortrait role={agent} size="sm" /> : null}
          <T style={styles.title} numberOfLines={lines}>
            {title}
          </T>
        </View>
        {sub ? (
          <T variant="detalle" soft numberOfLines={lines}>
            {sub}
          </T>
        ) : null}
        <StateBadge badge={badge} />
        {children ? (
          <>
            <Pressable accessibilityRole="button" accessibilityState={{ expanded: open }} onPress={() => setOpen((value) => !value)} style={styles.link}>
              <T variant="detalle" color={colors.brandDeep}>
                {open ? 'Ver menos' : expandLabel}
              </T>
            </Pressable>
            {open ? <View style={styles.content}>{children}</View> : null}
          </>
        ) : null}
        <Links to={to} linkLabel={linkLabel} external={external} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  item: { flexDirection: 'row', alignItems: 'flex-start', gap: space[3], paddingVertical: space[3], borderTopWidth: 1, borderTopColor: colors.line },
  dot: { width: DOT, height: DOT, marginTop: 7, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.ink },
  time: { width: TIME_WIDTH, lineHeight: 24 },
  body: { flex: 1, minWidth: 0, gap: 2 },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: space[2] },
  title: { flex: 1 },
  badge: { alignSelf: 'flex-start', marginTop: space[1] },
  content: { gap: space[2], paddingTop: space[1] },
  links: { flexDirection: 'row', flexWrap: 'wrap', columnGap: space[4] },
  link: { minHeight: shell.touch, justifyContent: 'center', alignSelf: 'flex-start' },
  externalLink: { flexDirection: 'row', alignItems: 'center', gap: space[1] },
  compact: { borderTopWidth: 1, borderTopColor: colors.line },
  compactHead: { minHeight: shell.touch, flexDirection: 'row', alignItems: 'center', gap: space[3], paddingVertical: space[1] },
  // The dot sits on the first line of the sentence, also when it unfolds into several.
  compactDot: { alignSelf: 'flex-start', marginTop: space[1] + 7 },
  compactMore: { gap: 2, paddingLeft: BODY_INDENT, paddingBottom: space[2] },
});
