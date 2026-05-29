import { SportConfigBody, SportConfigResponse } from '@openapi';
import useSWR, { SWRResponse } from 'swr';
import { createAxios, handleRequestError } from './adapter';

const fetcher = (url: string) =>
  createAxios()
    .get(url)
    .then((res: { data: any }) => res.data);

export function getSportConfig(tournament_id: number): SWRResponse<SportConfigResponse> {
  return useSWR(`tournaments/${tournament_id}/sport-config`, fetcher);
}

export function getSportPresets(): SWRResponse<Record<string, SportConfigBody>> {
  return useSWR('sport-presets', fetcher);
}

export async function updateSportConfig(tournament_id: number, body: SportConfigBody) {
  return createAxios()
    .put(`tournaments/${tournament_id}/sport-config`, body)
    .catch((response: any) => handleRequestError(response));
}

export async function deleteSportConfig(tournament_id: number) {
  return createAxios()
    .delete(`tournaments/${tournament_id}/sport-config`)
    .catch((response: any) => handleRequestError(response));
}
