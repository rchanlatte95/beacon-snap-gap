import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { createHttpAskService } from './ai/askClient'
import { OpportunitiesApp } from './App'

const root = document.getElementById('root')
if (!root) throw new Error('index.html has no #root element')

const askService = createHttpAskService()

createRoot(root).render(
  <StrictMode>
    <OpportunitiesApp askService={askService} />
  </StrictMode>,
)
