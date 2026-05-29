import {
  Button,
  Checkbox,
  Grid,
  Image,
  Modal,
  NumberInput,
  Select,
  Switch,
  TextInput,
} from '@mantine/core';
import { DateTimePicker } from '@mantine/dates';
import { useForm } from '@mantine/form';
import { GoPlus } from '@react-icons/all-files/go/GoPlus';
import { IconCalendar, IconCalendarTime } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import SaveButton from '@components/buttons/save';
import { assert_not_none } from '@components/utils/assert';
import { Club, Tournament, TournamentsResponse } from '@openapi';
import { getBaseApiUrl, getClubs } from '@services/adapter';
import { getSportPresets } from '@services/sport_config';
import { createTournament } from '@services/tournament';
import dayjs from 'dayjs';

export function TournamentLogo({ tournament }: { tournament: Tournament | null }) {
  if (tournament == null || tournament.logo_path == null) return null;
  return (
    <Image
      radius="md"
      alt="Logo of the tournament"
      src={`${getBaseApiUrl()}/static/tournament-logos/${tournament.logo_path}`}
    />
  );
}

function GeneralTournamentForm({
  setOpened,
  swrTournamentsResponse,
  clubs,
}: {
  setOpened: any;
  swrTournamentsResponse: SWRResponse<TournamentsResponse>;
  clubs: Club[];
}) {
  const { t } = useTranslation();
  const swrPresetsResponse = getSportPresets();
  const presets = swrPresetsResponse.data ?? {};
  const presetOptions = [
    ...Object.keys(presets).map((name) => ({ value: name, label: name })),
    { value: '__custom__', label: t('custom_sport_label') },
  ];

  const form = useForm({
    initialValues: {
      start_time: dayjs(),
      name: '',
      club_id: null,
      dashboard_public: true,
      dashboard_endpoint: '',
      players_can_be_in_multiple_teams: false,
      auto_assign_courts: true,
      duration_minutes: 10,
      margin_minutes: 5,
      enable_set_scoring: false,
      preset: null as string | null,
      sport_name: 'Custom',
      num_sets: 3,
      points_per_set: null as number | null,
      points_last_set: null as number | null,
      min_point_difference: null as number | null,
      max_score: null as number | null,
    },

    validate: {
      name: (value) => (value.length > 0 ? null : t('too_short_name_validation')),
      club_id: (value) => (value != null ? null : t('club_choose_title')),
      start_time: (value) => (value != null ? null : t('start_time_choose_title')),
      duration_minutes: (value) =>
        value != null && value > 0 ? null : t('duration_minutes_choose_title'),
      margin_minutes: (value) =>
        value != null && value > 0 ? null : t('margin_minutes_choose_title'),
    },
  });

  return (
    <form
      onSubmit={form.onSubmit(async (values) => {
        const sportConfig = values.enable_set_scoring
          ? {
              name: values.sport_name,
              num_sets: values.num_sets,
              points_per_set: values.points_per_set,
              points_last_set: values.points_last_set,
              min_point_difference: values.min_point_difference,
              max_score: values.max_score,
            }
          : null;

        await createTournament(
          parseInt(assert_not_none(values.club_id as unknown as string), 10),
          values.name,
          values.dashboard_public,
          values.dashboard_endpoint,
          values.players_can_be_in_multiple_teams,
          values.auto_assign_courts,
          values.start_time,
          values.duration_minutes,
          values.margin_minutes,
          sportConfig
        );

        await swrTournamentsResponse.mutate();
        setOpened(false);
      })}
    >
      <TextInput
        withAsterisk
        label={t('name_input_label')}
        placeholder={t('tournament_name_input_placeholder')}
        {...form.getInputProps('name')}
      />

      <Select
        withAsterisk
        data={clubs.map((p) => ({ value: `${p.id}`, label: p.name }))}
        label={t('club_select_label')}
        placeholder={t('club_select_placeholder')}
        searchable
        limit={20}
        style={{ marginTop: 10 }}
        {...form.getInputProps('club_id')}
      />

      <TextInput
        label={t('dashboard_link_label')}
        placeholder={t('dashboard_link_placeholder')}
        mt="lg"
        {...form.getInputProps('dashboard_endpoint')}
      />
      <Grid mt="1rem">
        <Grid.Col span={{ sm: 9 }}>
          <DateTimePicker
            leftSection={<IconCalendar size="1.1rem" stroke={1.5} />}
            mx="auto"
            {...form.getInputProps('start_time')}
          />
        </Grid.Col>
        <Grid.Col span={{ sm: 3 }}>
          <Button
            fullWidth
            color="indigo"
            leftSection={<IconCalendarTime size="1.1rem" stroke={1.5} />}
            onClick={() => {
              form.setFieldValue('start_time', dayjs());
            }}
          >
            {t('now_button')}
          </Button>
        </Grid.Col>
      </Grid>

      <Grid>
        <Grid.Col span={{ sm: 6 }}>
          <NumberInput
            label={t('match_duration_label')}
            mt="lg"
            {...form.getInputProps('duration_minutes')}
          />
        </Grid.Col>
        <Grid.Col span={{ sm: 6 }}>
          <NumberInput
            label={t('time_between_matches_label')}
            mt="lg"
            {...form.getInputProps('margin_minutes')}
          />
        </Grid.Col>
      </Grid>

      <Switch
        mt="lg"
        label={t('enable_set_scoring_label')}
        checked={form.values.enable_set_scoring}
        onChange={(event) => {
          form.setFieldValue('enable_set_scoring', event.currentTarget.checked);
          if (!event.currentTarget.checked) {
            form.setFieldValue('preset', null);
          }
        }}
      />

      {form.values.enable_set_scoring && (
        <>
          <Select
            label={t('preset_label')}
            placeholder={t('preset_placeholder')}
            data={presetOptions}
            mt="md"
            value={form.values.preset}
            onChange={(value) => {
              form.setFieldValue('preset', value);
              if (value && value !== '__custom__' && presets[value]) {
                const p = presets[value];
                form.setFieldValue('sport_name', p.name);
                form.setFieldValue('num_sets', p.num_sets);
                form.setFieldValue('points_per_set', p.points_per_set);
                form.setFieldValue('points_last_set', p.points_last_set);
                form.setFieldValue('min_point_difference', p.min_point_difference);
                form.setFieldValue('max_score', p.max_score);
              } else if (value === '__custom__') {
                form.setFieldValue('sport_name', 'Custom');
              }
            }}
          />
          <TextInput label={t('sport_name_label')} mt="md" {...form.getInputProps('sport_name')} />
          <NumberInput
            label={t('num_sets_label')}
            mt="md"
            min={1}
            max={9}
            {...form.getInputProps('num_sets')}
          />
          <Grid>
            <Grid.Col span={{ sm: 6 }}>
              <NumberInput
                label={t('points_per_set_label')}
                mt="md"
                min={1}
                {...form.getInputProps('points_per_set')}
              />
            </Grid.Col>
            <Grid.Col span={{ sm: 6 }}>
              <NumberInput
                label={t('points_last_set_label')}
                mt="md"
                min={1}
                {...form.getInputProps('points_last_set')}
              />
            </Grid.Col>
          </Grid>
          <Grid>
            <Grid.Col span={{ sm: 6 }}>
              <NumberInput
                label={t('min_point_difference_label')}
                mt="md"
                min={1}
                {...form.getInputProps('min_point_difference')}
              />
            </Grid.Col>
            <Grid.Col span={{ sm: 6 }}>
              <NumberInput
                label={t('max_score_label')}
                mt="md"
                min={1}
                {...form.getInputProps('max_score')}
              />
            </Grid.Col>
          </Grid>
        </>
      )}

      <Checkbox
        mt="md"
        label={t('dashboard_public_description')}
        {...form.getInputProps('dashboard_public', { type: 'checkbox' })}
      />
      <Checkbox
        mt="md"
        label={t('miscellaneous_label')}
        {...form.getInputProps('players_can_be_in_multiple_teams', { type: 'checkbox' })}
      />
      <Checkbox
        mt="md"
        label={t('auto_assign_courts_label')}
        {...form.getInputProps('auto_assign_courts', { type: 'checkbox' })}
      />

      <Button fullWidth mt={8} color="green" type="submit">
        {t('save_button')}
      </Button>
    </form>
  );
}

export default function TournamentModal({
  swrTournamentsResponse,
}: {
  swrTournamentsResponse: SWRResponse<TournamentsResponse>;
}) {
  const { t } = useTranslation();
  const [opened, setOpened] = useState(false);
  const operation_text = t('create_tournament_button');
  const swrClubsResponse = getClubs();
  const clubs = swrClubsResponse.data?.data || [];

  return (
    <>
      <Modal opened={opened} onClose={() => setOpened(false)} title={operation_text} size="50rem">
        <GeneralTournamentForm
          setOpened={setOpened}
          swrTournamentsResponse={swrTournamentsResponse}
          clubs={clubs}
        />
      </Modal>
      <SaveButton
        mx="0px"
        fullWidth
        onClick={() => setOpened(true)}
        leftSection={<GoPlus size={24} />}
        title={operation_text}
      />
    </>
  );
}
