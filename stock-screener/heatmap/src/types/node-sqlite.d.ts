declare module "node:sqlite" {
  export type DatabaseSyncOptions = {
    open?: boolean;
    readOnly?: boolean;
    enableForeignKeyConstraints?: boolean;
    enableDoubleQuotedStringLiterals?: boolean;
  };

  export class StatementSync {
    all(...anonymousParameters: unknown[]): unknown[];
    get(...anonymousParameters: unknown[]): unknown;
  }

  export class DatabaseSync {
    constructor(location: string, options?: DatabaseSyncOptions);
    prepare(sql: string): StatementSync;
    close(): void;
  }
}
