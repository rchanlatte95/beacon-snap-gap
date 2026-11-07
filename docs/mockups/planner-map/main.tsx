// Entry for the planner-map mock-up. Served by `npm run dev` at /docs/mockups/planner-map/.
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { MockApp } from './PlannerMock'

const root = document.getElementById('root')
if (!root) throw new Error('index.html has no #root element')
createRoot(root).render(
  <StrictMode>
    <MockApp />
  </StrictMode>,
)
