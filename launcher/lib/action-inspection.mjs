import {assert} from './storage.mjs';
import {currentActionInspection,actionInspectionRefresh} from '../public/action-inspection.mjs';
export async function assertCurrentActionInspection(work,run){
  assert(currentActionInspection(run,await work.available()),actionInspectionRefresh,409);
}
