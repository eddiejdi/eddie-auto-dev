package main

import (
	"fmt"
	"log"
)

// JiraClient é uma interface para a API do Jira
type JiraClient interface {
	CreateIssue(title string, description string) error
	UpdateIssue(issueID int, title string, description string) error
}

// GoAgent integrado com Jira
func GoAgent(jiraClient JiraClient) {
	// Simulação de atividades
	for i := 1; i <= 5; i++ {
		title := fmt.Sprintf("Atividade %d", i)
		description := fmt.Sprintf("Descrição da atividade %d", i)

		if err := jiraClient.CreateIssue(title, description); err != nil {
			log.Printf("Erro ao criar issue: %v\n", err)
			continue
		}

		fmt.Printf("Issue criado com ID %d\n", i)

		// Simulação de atualização da atividade
		time.Sleep(2 * time.Second)

		if err := jiraClient.UpdateIssue(i, title, description); err != nil {
			log.Printf("Erro ao atualizar issue: %v\n", err)
			continue
		}

		fmt.Printf("Issue atualizado com ID %d\n", i)
	}
}

func main() {
	// Simulação de Jira Client (pode ser substituído por uma implementação real)
	jiraClient := &JiraClientMock{}

	GoAgent(jiraClient)

	if __name__ == "__main__":