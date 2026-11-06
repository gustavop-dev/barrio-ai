CREATE TABLE `relay_requests` (
	`id` text PRIMARY KEY NOT NULL,
	`owner` text NOT NULL,
	`operation` text NOT NULL,
	`body` text NOT NULL,
	`fingerprint` text NOT NULL,
	`state` text NOT NULL,
	`created` integer NOT NULL,
	`expires` integer NOT NULL,
	`claim` text,
	`result` text,
	`http_status` integer,
	`completed` integer
);
--> statement-breakpoint
CREATE INDEX `relay_queue` ON `relay_requests` (`state`,`created`);--> statement-breakpoint
CREATE INDEX `relay_owner` ON `relay_requests` (`owner`,`created`);--> statement-breakpoint
CREATE TABLE `relay_state` (
	`id` text PRIMARY KEY NOT NULL,
	`heartbeat` integer DEFAULT 0 NOT NULL,
	`viewer_seen` integer DEFAULT 0 NOT NULL,
	`summary` text DEFAULT '{}' NOT NULL
);
