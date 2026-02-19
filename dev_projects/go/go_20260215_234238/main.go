package main

import (
	"fmt"
	"log"
)

// JiraClient representa a interface para interagir com o Jira API
type JiraClient struct {
	url    string
	token  string
	client *http.Client
}

// NewJiraClient cria uma nova instância de JiraClient
func NewJiraClient(url, token string) *JiraClient {
	return &JiraClient{
		url:    url,
		token:  token,
		client: &http.Client{},
	}
}

// CreateIssue cria um novo issue no Jira
func (jc *JiraClient) CreateIssue(summary, description string) error {
	req, err := http.NewRequest("POST", jc.url+"/rest/api/2/issue", strings.NewReader(fmt.Sprintf(`{
		"fields": {
			"project": {"key": "YOUR_PROJECT_KEY"},
			"summary": "%s",
			"description": "%s"
		}
	}`, summary, description)))
	if err != nil {
		return fmt.Errorf("failed to create issue: %v", err)
	}

	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", jc.token))
	req.Header.Set("Content-Type", "application/json")

	resp, err := jc.client.Do(req)
	if err != nil {
		return fmt.Errorf("failed to create issue: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("issue creation failed with status code %d", resp.StatusCode)
	}

	fmt.Println("Issue created successfully")
	return nil
}

func main() {
	jc := NewJiraClient("https://your-jira-instance.atlassian.net/rest/api/2/", "YOUR_JIRA_TOKEN")

	err := jc.CreateIssue("My New Issue", "This is a test issue created by Go Agent.")
	if err != nil {
		log.Fatalf("Error creating issue: %v", err)
	}
}