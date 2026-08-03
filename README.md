# mailchimp-mcp

MCP server for full Mailchimp management: audiences, tags, segments,
campaigns, templates and reporting.

## Tools (40)

### Audience
| Tool | What it does |
|---|---|
| `get_lists` | All audiences with stats |
| `get_list_members` | Members with status/tag filters |
| `get_member` | Full contact data by email |
| `upsert_member` | Create or update a contact (never duplicates) |
| `archive_member` | Unsubscribe (not a permanent delete) |
| `search_members` | Search across all audiences |
| `get_member_activity` | Last 50 events for a contact |

### Tags
| Tool | What it does |
|---|---|
| `get_tags` | All tags for an audience |
| `update_member_tags` | Add/remove tags on an existing contact |

### Merge fields
| Tool | What it does |
|---|---|
| `get_merge_fields` | Custom fields for an audience |
| `create_merge_field` | Create a new field (CITY, BIRTHDAY...) |

### Segments
| Tool | What it does |
|---|---|
| `get_segments` | Saved segments with their IDs |
| `create_segment` | Create a segment by conditions or as a static list |
| `add_members_to_segment` | Add emails to an existing static segment |
| `remove_members_from_segment` | Remove emails from a static segment |
| `delete_segment` | Delete a saved segment (doesn't delete contacts) |

### Batch (bulk sync)
| Tool | What it does |
|---|---|
| `batch_upsert_members` | Upsert many contacts in a single call |
| `get_batch_status` | Poll batch progress |

### Campaigns
| Tool | What it does |
|---|---|
| `get_campaigns` | List campaigns with filters |
| `get_campaign` | Campaign details |
| `create_campaign` | New draft campaign |
| `update_campaign` | Update subject, from, segment... |
| `replicate_campaign` | Duplicate an existing campaign |
| `delete_campaign` | Delete a draft |

### Content and design
| Tool | What it does |
|---|---|
| `get_campaign_content` | Read a campaign's current HTML |
| `set_campaign_content` | Write the campaign's HTML |
| `send_test_email` | Send a test before the real send |
| `get_send_checklist` | Check requirements before sending |

### Sending
| Tool | What it does |
|---|---|
| `send_campaign` | Send immediately |
| `schedule_campaign` | Schedule for a date/time |
| `unschedule_campaign` | Cancel a scheduled send |
| `create_resend` | Resend to non-openers |

### Templates
| Tool | What it does |
|---|---|
| `get_templates` | List available templates |
| `create_template` | Create a reusable template from HTML |
| `update_template` | Update an existing template |

### Reporting
| Tool | What it does |
|---|---|
| `get_campaign_report` | Full report (opens, clicks, unsubscribes, bounces) |
| `get_campaign_advice` | Mailchimp's automatic suggestions |
| `get_campaign_click_details` | Clicks by URL |
| `get_campaign_open_details` | Who opened, open count and date |
| `get_campaign_unsubscribes` | Contacts who unsubscribed after the campaign |

## Recommended flow to design and send a campaign

```
1. get_campaigns(status="save")           → find the draft campaign
2. get_campaign(campaign_id)              → check current settings
3. update_campaign(...)                   → adjust subject, preview text, segment
4. set_campaign_content(html=...)         → design the email
5. send_test_email(test_emails=[...])     → check rendering
6. get_send_checklist(campaign_id)        → verify everything is ready
7. schedule_campaign(...) / send_campaign → send or schedule
8. get_campaign_report(campaign_id)       → review post-send metrics
9. create_resend(campaign_id)             → optional: resend to non-openers
```

## Bulk sync flow

```
1. batch_upsert_members(list_id, members=[...])   → returns batch_id
2. get_batch_status(batch_id)                      → poll until status="finished"
```

Turns thousands of individual API calls into one call + polling.

## Setup

1. Get your API key: Mailchimp → Account → Extras → API keys. The
   datacenter (e.g. `us17`) is the suffix after the dash — the server
   extracts it automatically.
2. Install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

## MCP client configuration

```json
{
  "mcpServers": {
    "mailchimp": {
      "command": "/path/to/.venv/bin/python3",
      "args": ["/path/to/mailchimp-mcp/server.py"],
      "env": {
        "MAILCHIMP_API_KEY": "<your-api-key>-usXX"
      }
    }
  }
}
```

## License

MIT — see [LICENSE](LICENSE).
