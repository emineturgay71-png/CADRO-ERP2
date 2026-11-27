import _ from "@/lib/translate"
import { useMemo, useState } from "react"
import { useFrappeGetDocList } from "frappe-react-sdk"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Loader2Icon, SearchIcon } from "lucide-react"

type GLEntryRow = {
    name: string
    account: string
    posting_date: string
    voucher_type: string
    voucher_no: string
    debit: number
    credit: number
    remarks?: string | null
    party?: string | null
    party_type?: string | null
    cost_center?: string | null
    against?: string | null
}

const GeneralLedger = () => {
    const [search, setSearch] = useState("")
    const [voucherType, setVoucherType] = useState<string | "">("")
    const { data, isLoading, error } = useFrappeGetDocList<GLEntryRow>("GL Entry", {
        fields: ["name", "account", "posting_date", "voucher_type", "voucher_no", "debit", "credit", "remarks", "party", "party_type", "cost_center", "against"],
        orderBy: { field: "posting_date", order: "desc" },
        limit: 100,
    })

    const filtered = useMemo(() => {
        if (!data) return []
        return data
            .filter(r => search === "" || r.account.toLowerCase().includes(search.toLowerCase()) || (r.voucher_no || "").toLowerCase().includes(search.toLowerCase()))
            .filter(r => voucherType === "" || r.voucher_type === voucherType)
    }, [data, search, voucherType])

    if (error) return <div className="p-4 text-destructive">{_("Failed to load general ledger.")}</div>

    return (
        <div className="flex flex-col gap-4">
            <div className="flex items-center gap-4">
                <div className="relative flex-1 max-w-sm">
                    <SearchIcon className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
                    <Input
                        className="pl-8"
                        placeholder={_("Search account or voucher...")}
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                    />
                </div>
                <Select value={voucherType} onValueChange={setVoucherType}>
                    <SelectTrigger className="w-48">
                        <SelectValue placeholder={_("All Vouchers")} />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="">{_("All Vouchers")}</SelectItem>
                        <SelectItem value="Sales Invoice">{_("Sales Invoice")}</SelectItem>
                        <SelectItem value="Purchase Invoice">{_("Purchase Invoice")}</SelectItem>
                        <SelectItem value="Payment Entry">{_("Payment Entry")}</SelectItem>
                        <SelectItem value="Journal Entry">{_("Journal Entry")}</SelectItem>
                    </SelectContent>
                </Select>
            </div>

            {isLoading ? (
                <div className="flex items-center justify-center p-16"><Loader2Icon className="size-6 animate-spin text-muted-foreground" /></div>
            ) : (
                <div className="border rounded-lg overflow-hidden">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>{_("Date")}</TableHead>
                                <TableHead>{_("Account")}</TableHead>
                                <TableHead>{_("Voucher")}</TableHead>
                                <TableHead className="text-end">{_("Debit")}</TableHead>
                                <TableHead className="text-end">{_("Credit")}</TableHead>
                                <TableHead>{_("Party")}</TableHead>
                                <TableHead>{_("Cost Center")}</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {filtered.map(r => (
                                <TableRow key={r.name}>
                                    <TableCell className="text-sm">{r.posting_date}</TableCell>
                                    <TableCell className="font-medium">{r.account}</TableCell>
                                    <TableCell className="text-sm text-muted-foreground">{r.voucher_type} {r.voucher_no}</TableCell>
                                    <TableCell className="text-end text-sm">{r.debit > 0 ? r.debit.toFixed(2) : "-"}</TableCell>
                                    <TableCell className="text-end text-sm">{r.credit > 0 ? r.credit.toFixed(2) : "-"}</TableCell>
                                    <TableCell className="text-sm">{r.party ?? "-"}</TableCell>
                                    <TableCell className="text-sm">{r.cost_center ?? "-"}</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            )}
        </div>
    )
}

export default GeneralLedger
