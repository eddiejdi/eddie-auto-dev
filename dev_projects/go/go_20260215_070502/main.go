package main

import (
	"fmt"
	"net/http"
)

// JiraAPI represents the API for interacting with Jira
type JiraAPI struct {
	URL string
}

// CreateIssue creates a new issue in Jira
func (j *JiraAPI) CreateIssue(title, description string) error {
	req, err := http.NewRequest("POST", j.URL+"/rest/api/2/issue", nil)
	if err != nil {
		return fmt.Errorf("failed to create issue: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")

	payload := `{
		"fields": {
			"project": {
				"id": "YOUR_PROJECT_ID"
			},
			"summary": "`+title+`",
			"description": "`+description+`"
		}
	}`

	req.Body = strings.NewReader(payload)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to create issue: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("failed to create issue: status code %d", resp.StatusCode)
	}

	fmt.Println("Issue created successfully")
	return nil
}

// Main function for the Go Agent integration with Jira
func main() {
	jira := &JiraAPI{
		URL: "https://your-jira-instance.atlassian.net",
	}

	if err := jira.CreateIssue("New Feature", "Implement a new feature in the application"); err != nil {
		fmt.Println(err)
	}
}