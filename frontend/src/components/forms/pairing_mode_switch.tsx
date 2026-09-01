import { ActionIcon, Group, Switch, Tooltip } from '@mantine/core';
import { UseFormReturnType } from '@mantine/form';
import { IconInfoCircle } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

export function PairingModeSwitch({ form }: { form: UseFormReturnType<any> }) {
  const { t } = useTranslation();
  return (
    <Group mt="md" wrap="nowrap" align="center">
      <Switch
        label={t('pairing_mode_switch_label')}
        {...form.getInputProps('pairing_mode_competitive', { type: 'checkbox' })}
      />
      <Tooltip label={t('pairing_mode_tooltip')} multiline w={340} withArrow>
        <ActionIcon
          variant="subtle"
          color="gray"
          size="sm"
          aria-label={t('pairing_mode_switch_label')}
        >
          <IconInfoCircle size={18} />
        </ActionIcon>
      </Tooltip>
    </Group>
  );
}
