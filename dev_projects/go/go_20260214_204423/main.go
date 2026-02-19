package main

import (
	"fmt"
	"net/http"
)

// JiraClient representa a interface para interagir com Jira API
type JiraClient struct {
	url    string
	token  string
}

// NewJiraClient cria uma nova instância de JiraClient
func NewJiraClient(url, token string) *JiraClient {
	return &JiraClient{
		url: url,
		token: token,
	}
}

// CreateIssue cria um novo issue em Jira
func (c *JiraClient) CreateIssue(summary, description string) error {
	req, err := http.NewRequest("POST", c.url+"/rest/api/2/issue", nil)
	if err != nil {
		return err
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", c.token))

	body := `{
		"fields": {
			"project": {"key": "YOUR_PROJECT_KEY"},
			"summary": "%s",
			"description": "%s"
		}
	}`

	req.Body = strings.NewReader(body)

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("Failed to create issue: %s", resp.Status)
	}

	fmt.Println("Issue created successfully")
	return nil
}

func main() {
	client := NewJiraClient("https://your-jira-instance.atlassian.net", "YOUR_JIRA_TOKEN")

	err := client.CreateIssue("Test Issue", "This is a test issue created by Go Agent.")
	if err != nil {
		fmt.Println(err)
	}
}