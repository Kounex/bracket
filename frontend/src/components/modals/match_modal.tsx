import {
  ActionIcon,
  Badge,
  Button,
  Center,
  Checkbox,
  Divider,
  Grid,
  Group,
  Modal,
  NumberInput,
  Stack,
  Table,
  Text,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconPlus, IconTrash } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import DeleteButton from '@components/buttons/delete';
import { formatMatchInput1, formatMatchInput2 } from '@components/utils/match';
import { TournamentMinimal } from '@components/utils/tournament';
import {
  MatchSetBody,
  MatchWithDetails,
  RoundWithMatches,
  SportConfig,
  StagesWithStageItemsResponse,
} from '@openapi';
import { getMatchLookup, getStageItemLookup } from '@services/lookups';
import { deleteMatch, updateMatch } from '@services/match';
import { getSportConfig } from '@services/sport_config';

function MatchDeleteButton({
  tournamentData,
  match,
  swrStagesResponse,
  swrUpcomingMatchesResponse,
}: {
  tournamentData: TournamentMinimal;
  match: MatchWithDetails;
  swrStagesResponse: SWRResponse<StagesWithStageItemsResponse>;
  swrUpcomingMatchesResponse: SWRResponse | null;
}) {
  const { t } = useTranslation();
  return (
    <DeleteButton
      fullWidth
      onClick={async () => {
        await deleteMatch(tournamentData.id, match.id);
        await swrStagesResponse.mutate();
        if (swrUpcomingMatchesResponse != null) await swrUpcomingMatchesResponse.mutate();
      }}
      style={{ marginTop: '1rem' }}
      size="sm"
      title={t('remove_match_button')}
    />
  );
}

function getMaxScoreForSet(
  setIndex: number,
  numSets: number,
  sportConfig: SportConfig
): number | undefined {
  if (sportConfig.max_score != null) return sportConfig.max_score;

  const isLastSet = setIndex === numSets - 1;
  const base =
    isLastSet && sportConfig.points_last_set != null
      ? sportConfig.points_last_set
      : sportConfig.points_per_set;
  if (base == null) return undefined;

  if (sportConfig.min_point_difference != null && sportConfig.min_point_difference > 1) {
    return base + sportConfig.min_point_difference - 1;
  }
  return base;
}

function SetScoreGrid({
  sets,
  onSetsChange,
  maxSets,
  sportConfig,
  team1Name,
  team2Name,
  t,
}: {
  sets: MatchSetBody[];
  onSetsChange: (sets: MatchSetBody[]) => void;
  maxSets: number;
  sportConfig: SportConfig;
  team1Name: string;
  team2Name: string;
  t: any;
}) {
  const addSet = () => {
    if (sets.length >= maxSets) return;
    onSetsChange([...sets, { set_number: sets.length + 1, score1: 0, score2: 0 }]);
  };

  const removeSet = (index: number) => {
    const newSets = sets.filter((_, i) => i !== index).map((s, i) => ({ ...s, set_number: i + 1 }));
    onSetsChange(newSets);
  };

  const updateSetScore = (index: number, field: 'score1' | 'score2', value: number) => {
    const clamped = Math.max(0, value);
    const newSets = [...sets];
    newSets[index] = { ...newSets[index], [field]: clamped };
    onSetsChange(newSets);
  };

  const setsWon1 = sets.filter((s) => s.score1 > s.score2).length;
  const setsWon2 = sets.filter((s) => s.score2 > s.score1).length;

  return (
    <Stack gap="sm">
      <Table striped highlightOnHover withTableBorder>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{t('set_label')}</Table.Th>
            <Table.Th>{team1Name}</Table.Th>
            <Table.Th>{team2Name}</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {sets.map((set, index) => {
            const maxScore = getMaxScoreForSet(index, maxSets, sportConfig);
            return (
              <Table.Tr key={set.set_number}>
                <Table.Td>
                  <Text fw={500}>{set.set_number}</Text>
                </Table.Td>
                <Table.Td>
                  <NumberInput
                    size="xs"
                    min={0}
                    max={maxScore}
                    value={set.score1}
                    onChange={(val) => updateSetScore(index, 'score1', Number(val) || 0)}
                    style={{ width: 80 }}
                  />
                </Table.Td>
                <Table.Td>
                  <NumberInput
                    size="xs"
                    min={0}
                    max={maxScore}
                    value={set.score2}
                    onChange={(val) => updateSetScore(index, 'score2', Number(val) || 0)}
                    style={{ width: 80 }}
                  />
                </Table.Td>
                <Table.Td>
                  <ActionIcon color="red" variant="subtle" onClick={() => removeSet(index)}>
                    <IconTrash size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>

      {sets.length < maxSets && (
        <Button variant="light" size="xs" leftSection={<IconPlus size={14} />} onClick={addSet}>
          {t('add_set_button')}
        </Button>
      )}

      <Group>
        <Badge color={setsWon1 > setsWon2 ? 'green' : 'gray'} variant="filled">
          {team1Name}: {setsWon1} {t('sets_won_label')}
        </Badge>
        <Badge color={setsWon2 > setsWon1 ? 'green' : 'gray'} variant="filled">
          {team2Name}: {setsWon2} {t('sets_won_label')}
        </Badge>
      </Group>
    </Stack>
  );
}

function MatchModalForm({
  tournamentData,
  match,
  swrStagesResponse,
  swrUpcomingMatchesResponse,
  setOpened,
  round,
}: {
  tournamentData: TournamentMinimal;
  match: MatchWithDetails | null;
  swrStagesResponse: SWRResponse<StagesWithStageItemsResponse>;
  swrUpcomingMatchesResponse: SWRResponse | null;
  setOpened: any;
  round: RoundWithMatches | null;
}) {
  if (match == null) {
    return null;
  }

  const { t } = useTranslation();
  const swrSportConfigResponse = getSportConfig(tournamentData.id);
  const sportConfig = swrSportConfigResponse.data?.data;
  const isSetBased = sportConfig != null;
  const maxSets = sportConfig?.num_sets ?? 3;

  const initialSets: MatchSetBody[] =
    match.sets && match.sets.length > 0
      ? match.sets.map((s) => ({ set_number: s.set_number, score1: s.score1, score2: s.score2 }))
      : [];

  const [sets, setSets] = useState<MatchSetBody[]>(initialSets);

  const form = useForm({
    initialValues: {
      stage_item_input1_score: match.stage_item_input1_score,
      stage_item_input2_score: match.stage_item_input2_score,
      custom_duration_minutes: match.custom_duration_minutes,
      custom_margin_minutes: match.custom_margin_minutes,
    },

    validate: {
      stage_item_input1_score: (value) => (value >= 0 ? null : t('negative_score_validation')),
      stage_item_input2_score: (value) => (value >= 0 ? null : t('negative_score_validation')),
      custom_duration_minutes: (value) =>
        value == null || value >= 0 ? null : t('negative_match_duration_validation'),
      custom_margin_minutes: (value) =>
        value == null || value >= 0 ? null : t('negative_match_margin_validation'),
    },
  });

  const [customDurationEnabled, setCustomDurationEnabled] = useState(
    match.custom_duration_minutes != null
  );
  const [customMarginEnabled, setCustomMarginEnabled] = useState(
    match.custom_margin_minutes != null
  );

  const stageItemsLookup = getStageItemLookup(swrStagesResponse);
  const matchesLookup = getMatchLookup(swrStagesResponse);

  const team1Name = formatMatchInput1(t, stageItemsLookup, matchesLookup, match);
  const team2Name = formatMatchInput2(t, stageItemsLookup, matchesLookup, match);

  return (
    <>
      <form
        onSubmit={form.onSubmit(async (values) => {
          const updatedMatch: any = {
            id: match.id,
            round_id: match.round_id,
            stage_item_input1_score: values.stage_item_input1_score,
            stage_item_input2_score: values.stage_item_input2_score,
            court_id: match.court_id || null,
            custom_duration_minutes: customDurationEnabled ? values.custom_duration_minutes : null,
            custom_margin_minutes: customMarginEnabled ? values.custom_margin_minutes : null,
          };

          if (isSetBased) {
            updatedMatch.sets = sets;
          }

          await updateMatch(tournamentData.id, match.id, updatedMatch);
          await swrStagesResponse.mutate();
          if (swrUpcomingMatchesResponse != null) await swrUpcomingMatchesResponse.mutate();
          setOpened(false);
        })}
      >
        {isSetBased ? (
          <SetScoreGrid
            sets={sets}
            onSetsChange={setSets}
            maxSets={maxSets}
            sportConfig={sportConfig}
            team1Name={team1Name}
            team2Name={team2Name}
            t={t}
          />
        ) : (
          <>
            <NumberInput
              withAsterisk
              label={`${t('score_of_label')} ${team1Name}`}
              placeholder={`${t('score_of_label')} ${team1Name}`}
              {...form.getInputProps('stage_item_input1_score')}
            />
            <NumberInput
              withAsterisk
              mt="lg"
              label={`${t('score_of_label')} ${team2Name}`}
              placeholder={`${t('score_of_label')} ${team2Name}`}
              {...form.getInputProps('stage_item_input2_score')}
            />
          </>
        )}
        <Divider mt="lg" />

        <Text size="sm" mt="lg">
          {t('custom_match_duration_label')}
        </Text>
        <Grid align="center">
          <Grid.Col span={{ sm: 8 }}>
            <NumberInput
              disabled={!customDurationEnabled}
              rightSection={<Text>{t('minutes')}</Text>}
              placeholder={`${match.duration_minutes}`}
              rightSectionWidth={92}
              {...form.getInputProps('custom_duration_minutes')}
            />
          </Grid.Col>
          <Grid.Col span={{ sm: 4 }}>
            <Center>
              <Checkbox
                checked={customDurationEnabled}
                label={t('customize_checkbox_label')}
                onChange={(event) => {
                  setCustomDurationEnabled(event.currentTarget.checked);
                }}
              />
            </Center>
          </Grid.Col>
        </Grid>

        <Text size="sm" mt="lg">
          {t('custom_match_margin_label')}
        </Text>
        <Grid align="center">
          <Grid.Col span={{ sm: 8 }}>
            <NumberInput
              disabled={!customMarginEnabled}
              placeholder={`${match.margin_minutes}`}
              rightSection={<Text>{t('minutes')}</Text>}
              rightSectionWidth={92}
              {...form.getInputProps('custom_margin_minutes')}
            />
          </Grid.Col>
          <Grid.Col span={{ sm: 4 }}>
            <Center>
              <Checkbox
                checked={customMarginEnabled}
                label={t('customize_checkbox_label')}
                onChange={(event) => {
                  setCustomMarginEnabled(event.currentTarget.checked);
                }}
              />
            </Center>
          </Grid.Col>
        </Grid>

        <Button fullWidth style={{ marginTop: 20 }} color="green" type="submit">
          {t('save_button')}
        </Button>
      </form>
      {round && round.is_draft && (
        <MatchDeleteButton
          swrStagesResponse={swrStagesResponse}
          swrUpcomingMatchesResponse={swrUpcomingMatchesResponse}
          tournamentData={tournamentData}
          match={match}
        />
      )}
    </>
  );
}

export default function MatchModal({
  tournamentData,
  match,
  swrStagesResponse,
  swrUpcomingMatchesResponse,
  opened,
  setOpened,
  round,
}: {
  tournamentData: TournamentMinimal;
  match: MatchWithDetails | null;
  swrStagesResponse: SWRResponse<StagesWithStageItemsResponse>;
  swrUpcomingMatchesResponse: SWRResponse | null;
  opened: boolean;
  setOpened: any;
  round: RoundWithMatches | null;
}) {
  const { t } = useTranslation();

  return (
    <>
      <Modal opened={opened} onClose={() => setOpened(false)} title={t('edit_match_modal_title')}>
        <MatchModalForm
          swrStagesResponse={swrStagesResponse}
          swrUpcomingMatchesResponse={swrUpcomingMatchesResponse}
          tournamentData={tournamentData}
          match={match}
          setOpened={setOpened}
          round={round}
        />
      </Modal>
    </>
  );
}
