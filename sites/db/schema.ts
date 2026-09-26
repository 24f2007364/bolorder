import {sqliteTable,text,integer} from 'drizzle-orm/sqlite-core';
export const workspaces=sqliteTable('workspaces',{id:text('id').primaryKey(),version:integer('version').notNull().default(0),payload:text('payload').notNull(),updatedAt:text('updated_at').notNull()});
export const quotas=sqliteTable('quotas',{id:text('id').primaryKey(),count:integer('count').notNull().default(0)});
