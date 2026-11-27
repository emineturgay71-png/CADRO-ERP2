import _ from "@/lib/translate"
import { useState } from "react"
import { useFrappePostCall } from "frappe-react-sdk"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Loader2Icon } from "lucide-react"

type StatementRow = {
    account: string
    account_name: string
    indent?: number
    balance?: number
    debit?: number
    credit?: number
    parent_account?: string
    is_group?: number
}

const FinancialStatements = () => {
    const [company, setCompany] = useState<string>("")
    const { result, call, loading, error } = useFrappePostCall<{ message: StatementRow[] }>("run_doc_method")

    const runReport = (report: string) => {
        if (!company) return
        const filters = { company, as_dict: true }
        call({ docs: { doctype: report }, method: "execute", kwargs: { filters } })
    }

    const rows: StatementRow[] = (result?.message as unknown as StatementRow[]) ?? []

    return (
        <div className="flex flex-col gap-4">
            <div className="flex items-center gap-4">
                <Select value={company} onValueChange={setCompany}>
                    <SelectTrigger className="w-64">
                        <SelectValue placeholder={_("Select Company")} />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="CADRO Teknoloji A.Ş.">{_("CADRO Teknoloji A.Ş.")}</SelectItem>
                    </SelectContent>
                </Select>
                <Button onClick={() => runReport("Balance Sheet")} disabled={loading || !company} size="sm" variant="outline">
                    {loading ? <Loader2Icon className="size-4 animate-spin" /> : null}
                    {_("Balance Sheet")}
                </Button>
                <Button onClick={() => runReport("Profit and Loss Statement")} disabled={loading || !company} size="sm" variant="outline">
                    {loading ? <Loader2Icon className="size-4 animate-spin" /> : null}
                    {_("Profit & Loss")}
                </Button>
            </div>

            {error ? (
                <div className="p-4 text-destructive">{_("Failed to run report.")}</div>
            ) : rows.length > 0 ? (
                <div className="border rounded-lg overflow-hidden">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>{_("Account")}</TableHead>
                                <TableHead className="text-end">{_("Balance")}</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {rows.map((r, i) => (
                                <TableRow key={i}>
                                    <TableCell className="font-medium" style={{ paddingLeft: `${(r.indent ?? 0) * 16 + 16}px` }}>
                                        {r.account_name ?? r.account}
                                    </TableCell>
                                    <TableCell className="text-end text-sm">{(r.balance ?? r.debit ?? 0)?.toFixed(2)}</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            ) : null}
        </div>
    )
}

export default FinancialStatements
