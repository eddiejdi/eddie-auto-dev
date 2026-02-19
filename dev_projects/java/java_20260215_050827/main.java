import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.Issue;
import com.atlassian.jira.client.api.domain.SearchResult;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class JavaAgentJiraIntegrationApplication {

    public static void main(String[] args) {
        SpringApplication.run(JavaAgentJiraIntegrationApplication.class, args);
    }

    // Implementação da funcionalidade de monitoramento de atividades em Jira
    public void monitorarAtividades() {
        try (JiraClient client = new JiraClientBuilder("https://your-jira-server.com").build()) {

            // Executar uma busca para obter todas as issues do projeto
            SearchResult searchResult = client.searchService().searchByQuery("project=YOUR_PROJECT_KEY", null);

            for (Issue issue : searchResult.getIssues()) {
                System.out.println("Issue ID: " + issue.getId());
                System.out.println("Summary: " + issue.getSummary());
                // Adicione mais informações conforme necessário
            }

        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}