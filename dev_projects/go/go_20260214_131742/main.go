package main

import (
	"fmt"
	"net/http"
)

// JiraClient é a interface para interagir com o Jira API
type JiraClient interface {
	CreateIssue(title, description string) error
}

// GoAgentClient é a interface para interagir com o Go Agent API
type GoAgentClient interface {
	ScheduleJob(jobName string) error
}

// JiraAPI implementa a interface JiraClient para interagir com o Jira API
type JiraAPI struct{}

func (j *JiraAPI) CreateIssue(title, description string) error {
	// Implementação da função para criar um issue no Jira
	fmt.Printf("Creating issue: %s - %s\n", title, description)
	return nil
}

// GoAgentAPI implementa a interface GoAgentClient para interagir com o Go Agent API
type GoAgentAPI struct{}

func (g *GoAgentAPI) ScheduleJob(jobName string) error {
	// Implementação da função para schedule um job no Go Agent
	fmt.Printf("Scheduling job: %s\n", jobName)
	return nil
}

// JiraIntegrationHandler é a função que processa as requisições do HTTP server
func JiraIntegrationHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method == "POST" {
		title := r.FormValue("title")
		description := r.FormValue("description")

		jiraClient := &JiraAPI{}
		err := jiraClient.CreateIssue(title, description)
		if err != nil {
			http.Error(w, fmt.Sprintf("Failed to create issue: %s", err), http.StatusInternalServerError)
			return
		}

		fmt.Fprintf(w, "Issue created successfully\n")
	} else {
		http.Error(w, "Unsupported method", http.StatusMethodNotAllowed)
	}
}

func main() {
	http.HandleFunc("/jira-integration", JiraIntegrationHandler)

	fmt.Println("Starting HTTP server on port 8080...")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		fmt.Printf("Failed to start HTTP server: %s\n", err)
	}
}