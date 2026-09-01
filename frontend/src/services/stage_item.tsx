import { createAxios, handleRequestError } from './adapter';

export async function createStageItem(
  tournament_id: number,
  stage_id: number,
  type: string,
  team_count: number,
  pairing_mode: string
) {
  return createAxios()
    .post(`tournaments/${tournament_id}/stage_items`, { stage_id, type, team_count, pairing_mode })
    .catch((response: any) => handleRequestError(response));
}

export async function updateStageItem(
  tournament_id: number,
  stage_item_id: number,
  name: string,
  ranking_id: string,
  pairing_mode: string
) {
  return createAxios()
    .put(`tournaments/${tournament_id}/stage_items/${stage_item_id}`, {
      name,
      ranking_id,
      pairing_mode,
    })
    .catch((response: any) => handleRequestError(response));
}

export async function deleteStageItem(tournament_id: number, stage_item_id: number) {
  return createAxios()
    .delete(`tournaments/${tournament_id}/stage_items/${stage_item_id}`)
    .catch((response: any) => handleRequestError(response));
}
