/**
 * Functional operators to use with RXJS.
 *
 * The idea is that instead of doing mutable actions in the RXJS subscribe function, you instead build into an output
 * observables and throw that in the sink, which will save it to the datastore.
 *
 * Why? I am curious how this feels. It's fun to be able to see all the results! Plus, then downstream users don't have
 * to deal with confusion of `subscribe` and GC around observables!
 */

import { Datastore, Record, Schema, Table, AnyField } from "@lumino/datastore";
import {
  SchemasListType,
  SchemasObjectType,
  records,
  withTransaction,
} from "./helpers";
import { Observable, Subscription } from "rxjs";
import { concatInitial } from "./ObservableWithInitial";

// export type IdsOf<T extends Schema[]>= T[number]['id'];

// type DatastoreCreator<SCHEMAS extends Schema[]> = {
//     get: {[ID in IdsOf<SCHEMAS>]: ID}
// }

/**
 * Mapping of schema ids to updates for that schema
 */
type DatastoreUpdates<SCHEMAS extends SchemasListType<SchemasObjectType>> = {
  [ID in keyof SCHEMAS]?: Table.Update<SCHEMAS[ID]>;
};

/**
 * Function that returns an onservable of all records in a table, given the id of a table.
 */
type GetFn<
  SCHEMAS extends SchemasListType<SchemasObjectType>,
  ID extends keyof SCHEMAS
> = (schema: SCHEMAS[ID]) => Observable<Array<Record<SCHEMAS[ID]>>>;

/**
 * Pass in a way to get records from a schema and get back an observable of updates to the records
 */
type Pipeline<SCHEMAS extends SchemasListType<SchemasObjectType>> = (
  get: GetFn<SCHEMAS, keyof SCHEMAS>
) => Observable<DatastoreUpdates<SCHEMAS>>;

export function createPipeline<
  SCHEMAS extends SchemasListType<SchemasObjectType>
>(
  schemas: SCHEMAS,
  fn: (options: {
    records: { [ID in keyof SCHEMAS]: Observable<Array<Record<SCHEMAS[ID]>>> };
    create: {
      [ID in keyof SCHEMAS]: (
        update: Record.Update<SCHEMAS[ID]>
      ) => [string, DatastoreUpdates<SCHEMAS>];
    };
    update: {
      [ID in keyof SCHEMAS]: (
        update: Table.Update<SCHEMAS[ID]>
      ) => DatastoreUpdates<SCHEMAS>;
    };
    merge: (
      ...updates: DatastoreUpdates<SCHEMAS>[]
    ) => DatastoreUpdates<SCHEMAS>;
  }) => Observable<DatastoreUpdates<SCHEMAS>>
): Pipeline<SCHEMAS> {
  return (getFn) =>
    fn({
      records: Object.fromEntries(Object.keys(schemas).map((key: keyof SCHEMAS) => [key, getFn(schemas[key])])),
      create: {},
      update: {},

      merge: (...storeUpdates) =>
        storeUpdates.reduce(
          (
            prev: DatastoreUpdates<SCHEMAS>,
            current: DatastoreUpdates<SCHEMAS>
          ) => mergeObjects(l, r, ([l, r]) => l),
          {}
        ),
    });
}

export function connectPipeline<
  SCHEMAS extends SchemasListType<SchemasObjectType>
>(pipeline: Pipeline<SCHEMAS>, datastore: Datastore): Subscription {
  return pipeline((schema) =>
    concatInitial(records(datastore, schema))
  ).subscribe({
    next: (updates) =>
      withTransaction(datastore, () => {
        for (const [id, update] of Object.entries(updates)) {
          //   Make dummy schema with ID. Datastore.get just looks at id.
          datastore.get({ id, fields: {} }).update(update || {});
        }
      }),
  });
}

/**
 * Merge two objects, using the `fn` to compute the combination value with duplicate keys.
 */
function mergeObjects<T>(
  l: { [key: string]: T },
  r: { [key: string]: T },
  fn: (values: [T, T], key: string) => T
) {}
