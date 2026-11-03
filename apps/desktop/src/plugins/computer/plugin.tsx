import {
  type HermesPlugin,
  type RouteContribution,
  ROUTES_AREA,
  SIDEBAR_NAV_AREA,
  type SidebarNavContribution,
  host
} from '@hermes/plugin-sdk'

import { PersonalComputerView } from './view'

const COMPUTER_ROUTE = '/computer'

const plugin: HermesPlugin = {
  id: 'personal-computer',
  name: 'Personal Computer',
  description: 'A dedicated workspace for computer control, browser sessions, tasks, and approvals.',
  defaultEnabled: true,
  register(ctx) {
    ctx.registerMany([
      {
        id: 'page',
        area: ROUTES_AREA,
        data: { path: COMPUTER_ROUTE } satisfies RouteContribution,
        render: () => <PersonalComputerView />
      },
      {
        id: 'nav',
        area: SIDEBAR_NAV_AREA,
        order: 45,
        data: {
          codicon: 'device-desktop',
          label: 'Computer',
          path: COMPUTER_ROUTE
        } satisfies SidebarNavContribution
      }
    ])
  }
}

export default plugin
