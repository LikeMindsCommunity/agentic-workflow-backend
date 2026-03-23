# IVR Workflow Builder - API Documentation

## Overview
The IVR Workflow Builder allows you to create interactive voice response workflows that handle inbound calls. Workflows are defined as a graph of nodes connected by transitions.

## Workflow Object
A workflow is the top-level container. Each workflow has a unique ID, a name, and a set of nodes.

- `id`: Unique identifier, auto-generated. Format: `wf_ivr_XXX`
- `name`: Human-readable name
- `version`: Integer, incremented on each update
- `status`: One of `active`, `draft`, `archived`
- `entryPoint`: The ID of the first node to execute when a call comes in

## Node Types

### playback
Plays an audio file to the caller.
- `audioFile`: Path to the audio file (must be pre-uploaded)
- `interruptible`: Boolean. If true, caller can press a key to skip

### menu
Presents options to the caller via DTMF input.
- `prompt`: Audio file for the menu prompt
- `timeout`: Seconds to wait for input
- `retryCount`: How many times to replay the prompt on no input
- `options`: Array of digit-to-action mappings
- `fallbackAction`: What happens when retries are exhausted

### transfer
Transfers the call to a queue or agent.
- `target`: The queue ID to transfer to
- `priority`: Integer priority in the queue (lower = higher priority)
- `waitMusic`: Audio file to play while waiting
- `maxWaitTime`: Maximum seconds to wait before triggering onTimeout

## Queues
Queues must be pre-configured in the system. Transfers reference queues by their ID.
Available queue operations: route to agent, voicemail, callback request.

## Audio Files
All audio files must be uploaded before they can be referenced in workflows.
Supported formats: .wav, .mp3
Maximum duration: 120 seconds per file.

## Validation Rules
- Every node referenced in a `next` field must exist in the workflow
- The `entryPoint` must reference a valid node ID
- Menu options must have unique digits within the same menu node
- Transfer nodes must reference valid queue IDs
