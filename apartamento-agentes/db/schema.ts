import { sqliteTable, text, integer, index } from 'drizzle-orm/sqlite-core';
export const relayRequests = sqliteTable('relay_requests', {
 id:text('id').primaryKey(), owner:text('owner').notNull(), operation:text('operation').notNull(),
 body:text('body').notNull(), fingerprint:text('fingerprint').notNull(), state:text('state').notNull(),
 created:integer('created').notNull(), expires:integer('expires').notNull(), claim:text('claim'),
 result:text('result'), httpStatus:integer('http_status'), completed:integer('completed'),
}, t=>[index('relay_queue').on(t.state,t.created),index('relay_owner').on(t.owner,t.created)]);
export const relayState = sqliteTable('relay_state', {
 id:text('id').primaryKey(), heartbeat:integer('heartbeat').notNull().default(0),
 viewerSeen:integer('viewer_seen').notNull().default(0), summary:text('summary').notNull().default('{}'),
});
