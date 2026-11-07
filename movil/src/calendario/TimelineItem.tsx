// A row of the timeline (the PWA's TimelineItem): layer dot, hour, the sentence, an optional line under
// it, the state badge when it is not a normal success, the role's portrait, folded content and links.
import type { Tone } from '@compartido/logic/tone';
import { useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Icon } from '@/components/icons';
import { AgentPortrait, Badge, T } from '@/components/ui';
import { isHttps, openLink } from '@/navigation';
import { colors, radius, shell, space } from '@/theme/tokens';

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
  testID?: string;
}

export function TimelineItem({ color, time, title, sub, badge, agent, to, linkLabel = 'Abrir', externalUrl, children, expandLabel = 'Ver más', testID }: TimelineItemProps) {
  const [open, setOpen] = useState(false);
  const external = isHttps(externalUrl) ? externalUrl : null;
  return (
    <View style={styles.item} testID={testID}>
      <View style={[styles.dot, { backgroundColor: color }]} />
      <T variant="detalle" soft style={styles.time}>
        {time || ''}
      </T>
      <View style={styles.body}>
        <View style={styles.titleRow}>
          {agent ? <AgentPortrait role={agent} size="sm" /> : null}
          <T style={styles.title}>{title}</T>
        </View>
        {sub ? (
          <T variant="detalle" soft>
            {sub}
          </T>
        ) : null}
        {badge ? (
          <View style={styles.badge}>
            <Badge tone={badge.tone}>{badge.label}</Badge>
          </View>
        ) : null}
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
        {to || external ? (
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
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  item: { flexDirection: 'row', alignItems: 'flex-start', gap: space[3], paddingVertical: space[3], borderTopWidth: 1, borderTopColor: colors.line },
  dot: { width: 10, height: 10, marginTop: 7, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.ink },
  time: { width: 44, lineHeight: 24 },
  body: { flex: 1, minWidth: 0, gap: 2 },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: space[2] },
  title: { flex: 1 },
  badge: { alignSelf: 'flex-start', marginTop: space[1] },
  content: { gap: space[2], paddingTop: space[1] },
  links: { flexDirection: 'row', flexWrap: 'wrap', columnGap: space[4] },
  link: { minHeight: shell.touch, justifyContent: 'center', alignSelf: 'flex-start' },
  externalLink: { flexDirection: 'row', alignItems: 'center', gap: space[1] },
});
