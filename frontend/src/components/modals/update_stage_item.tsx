import { Button, Modal, TextInput } from '@mantine/core';
import { useForm } from '@mantine/form';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import { PairingModeSwitch } from '@components/forms/pairing_mode_switch';
import { RankingSelect } from '@components/select/ranking_select';
import { Ranking, StageItemWithRounds, StagesWithStageItemsResponse, Tournament } from '@openapi';
import { updateStageItem } from '@services/stage_item';

export function UpdateStageItemModal({
  tournament,
  opened,
  setOpened,
  stageItem,
  swrStagesResponse,
  rankings,
}: {
  tournament: Tournament;
  opened: boolean;
  setOpened: any;
  stageItem: StageItemWithRounds;
  swrStagesResponse: SWRResponse<StagesWithStageItemsResponse>;
  rankings: Ranking[];
}) {
  const { t } = useTranslation();
  const form = useForm({
    initialValues: {
      name: stageItem.name,
      ranking_id: rankings.filter((ranking) => ranking.position === 0)[0].id.toString(),
      pairing_mode_competitive: stageItem.pairing_mode === 'COMPETITIVE',
    },
    validate: {},
  });

  return (
    <Modal opened={opened} onClose={() => setOpened(false)} title={t('edit_stage_item_label')}>
      <form
        onSubmit={form.onSubmit(async (values) => {
          await updateStageItem(
            tournament.id,
            stageItem.id,
            values.name,
            values.ranking_id,
            values.pairing_mode_competitive ? 'COMPETITIVE' : 'SOCIAL'
          );
          await swrStagesResponse.mutate();
          setOpened(false);
        })}
      >
        <TextInput
          label={t('name_input_label')}
          placeholder=""
          required
          my="lg"
          type="text"
          {...form.getInputProps('name')}
        />
        <RankingSelect form={form} rankings={rankings} />
        {stageItem.type === 'SWISS' && <PairingModeSwitch form={form} />}
        <Button fullWidth style={{ marginTop: 16 }} color="green" type="submit">
          {t('save_button')}
        </Button>
      </form>
    </Modal>
  );
}
