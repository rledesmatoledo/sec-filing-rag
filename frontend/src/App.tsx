import { useState } from "react";
import { Authenticator } from "@aws-amplify/ui-react";
import { fetchAuthSession } from "aws-amplify/auth";

import {
  View,
  Heading,
  SelectField,
  TextField,
  Button,
  Text,
} from "@aws-amplify/ui-react";

import "@aws-amplify/ui-react/styles.css";

const COMPANIES: Record<string, string> = {
  Apple: "AAPL",
  Amazon: "AMZN",
  Microsoft: "MSFT",
  Google: "GOOGL",
  Meta: "META",
  Netflix: "NFLX",
};

const currentYear = new Date().getFullYear();
const years = Array.from({ length: 5 }, (_, i) => currentYear - i);

async function submitQuery(body: {
  question: string;
  ticker: string;
  year: number;
  period: string;
}) {
  const { tokens } = await fetchAuthSession();
  const idToken = tokens?.idToken?.toString() ?? "";

  const response = await fetch(
    "https://jqrinkg975.execute-api.us-east-1.amazonaws.com/inference",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: idToken,
      },
      body: JSON.stringify(body),
    }
  );
  if (!response.ok) throw new Error("API request failed");
  return await response.json();
}

function cleanAnswer(text: string): string {
  return text.replace(/\*\*/g, "").replace(/- /g, "\n• ");
}

function App() {
  const [company, setCompany] = useState("");
  const [year, setYear] = useState(currentYear.toString());
  const [period, setPeriod] = useState("Q1");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!company || !question) {
      setError("Please fill in all fields.");
      return;
    }

    setLoading(true);
    setError(null);
    setAnswer("");

    try {
      const result = await submitQuery({
        question,
        ticker: COMPANIES[company],
        year: parseInt(year),
        period,
      });
      const data = typeof result.body === "string" ? JSON.parse(result.body) : result;
      setAnswer(data.answer);
    } catch (e) {
      setError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Authenticator>
      {({ signOut }) => (
        <View padding="2rem" maxWidth="600px" margin="2rem auto">
          <Heading level={1}>Partner Bot</Heading>
          <Text marginBottom="1rem">
            Ask any question about a company's quarterly or annual financial reports.
          </Text>

          <SelectField
            label="Company"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            placeholder="Select a MLT partner company"
          >
            {Object.keys(COMPANIES).map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </SelectField>

          <SelectField
            label="Year"
            value={year}
            onChange={(e) => setYear(e.target.value)}
          >
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </SelectField>

          <SelectField
            label="Period"
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
          >
            <option value="Q1">Q1</option>
            <option value="Q2">Q2</option>
            <option value="Q3">Q3</option>
            <option value="Q4">Q4</option>
            <option value="FY">FY (Full Year)</option>
          </SelectField>

          <TextField
            label="Question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. What was total revenue this quarter?"
          />

          <Button
            variation="primary"
            onClick={handleSubmit}
            isLoading={loading}
            loadingText="Thinking..."
            marginTop="1rem"
            width="100%"
          >
            Ask
          </Button>

          {error && (
            <Text color="red" marginTop="1rem">
              {error}
            </Text>
          )}

          {answer && (
            <View
              marginTop="1rem"
              padding="1rem"
              backgroundColor="rgba(0,0,0,0.05)"
              borderRadius="8px"
            >
              <Heading level={4}>{company} — {period} {year}</Heading>
              <Text whiteSpace="pre-wrap">{cleanAnswer(answer)}</Text>
            </View>
          )}

          <Button onClick={signOut} marginTop="2rem" size="small">
            Sign Out
          </Button>
        </View>
      )}
    </Authenticator>
  );
}

export default App;